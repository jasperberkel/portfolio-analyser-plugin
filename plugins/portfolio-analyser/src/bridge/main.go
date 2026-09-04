package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"

	"github.com/zalando/go-keyring"
)

const (
	defaultBaseURL = "http://127.0.0.1:8010"
	keyringService = "portfolio-analyser"
	keyringAccount = "mcp-access-token"
	maxMessageSize = 16 << 20
)

type tokenStore interface {
	Get() (string, error)
	Set(string) error
}

type systemTokenStore struct{}

func (systemTokenStore) Get() (string, error) {
	return keyring.Get(keyringService, keyringAccount)
}

func (systemTokenStore) Set(token string) error {
	return keyring.Set(keyringService, keyringAccount, token)
}

type bridge struct {
	baseURL string
	store   tokenStore
	client  *http.Client
}

func main() {
	if len(os.Args) < 2 {
		fatal("usage: portfolio-analyser-bridge <pair|status|mcp>")
	}
	b := bridge{
		baseURL: defaultBaseURL,
		store:   systemTokenStore{},
		client:  &http.Client{Timeout: 5 * time.Minute},
	}

	var err error
	switch os.Args[1] {
	case "pair":
		err = runPairCommand(b, os.Args[2:], os.Stdin, os.Stdout)
	case "status":
		err = b.status(context.Background(), os.Stdout)
	case "mcp":
		err = b.serve(context.Background(), os.Stdin, os.Stdout)
	default:
		err = fmt.Errorf("unknown command %q", os.Args[1])
	}
	if err != nil {
		fatal(safeError(err))
	}
}

func runPairCommand(b bridge, args []string, input io.Reader, output io.Writer) error {
	flags := flag.NewFlagSet("pair", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	clientName := flags.String("client", "Portfolio Analyser Plugin", "client display name")
	platform := flags.String("platform", runtime.GOOS, "client platform")
	if err := flags.Parse(args); err != nil {
		return err
	}
	reader := bufio.NewReader(io.LimitReader(input, 128))
	code, err := reader.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return fmt.Errorf("read pairing code: %w", err)
	}
	code = strings.TrimSpace(code)
	if code == "" {
		return errors.New("no pairing code provided on stdin")
	}
	if err := b.pair(context.Background(), code, *clientName, *platform); err != nil {
		return err
	}
	_, err = fmt.Fprintln(output, "Portfolio Analyser connected securely.")
	return err
}

func (b bridge) pair(ctx context.Context, code, clientName, platform string) error {
	payload, err := json.Marshal(map[string]string{
		"code":        code,
		"client_name": clientName,
		"platform":    platform,
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx, http.MethodPost, b.baseURL+"/api/v1/mcp/pairings/exchange", bytes.NewReader(payload),
	)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	response, err := b.client.Do(req)
	if err != nil {
		return fmt.Errorf("Portfolio Analyser is not reachable at %s", b.baseURL)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("pairing was rejected with HTTP %d", response.StatusCode)
	}
	var result struct {
		Token string `json:"token"`
	}
	decoder := json.NewDecoder(io.LimitReader(response.Body, 4096))
	if err := decoder.Decode(&result); err != nil || result.Token == "" {
		return errors.New("pairing returned an invalid response")
	}
	if err := b.store.Set(result.Token); err != nil {
		return keyringStorageError(err)
	}
	return nil
}

func (b bridge) status(ctx context.Context, output io.Writer) error {
	token, err := b.store.Get()
	if err != nil {
		return keyringStorageError(err)
	}
	request := []byte(`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"portfolio-analyser-bridge","version":"0.4.1"}}}`)
	responses, err := b.forward(ctx, token, request, "2025-06-18")
	if err != nil {
		return err
	}
	if len(responses) == 0 {
		return errors.New("MCP server returned no initialization response")
	}
	_, err = fmt.Fprintln(output, "Portfolio Analyser MCP connection is ready.")
	return err
}

func (b bridge) serve(ctx context.Context, input io.Reader, output io.Writer) error {
	token, err := b.store.Get()
	if err != nil {
		return keyringStorageError(err)
	}
	scanner := bufio.NewScanner(input)
	scanner.Buffer(make([]byte, 64*1024), maxMessageSize)
	protocolVersion := ""
	for scanner.Scan() {
		message := bytes.TrimSpace(scanner.Bytes())
		if len(message) == 0 {
			continue
		}
		if version := initializeProtocolVersion(message); version != "" {
			protocolVersion = version
		}
		responses, requestErr := b.forward(ctx, token, message, protocolVersion)
		if requestErr != nil {
			if response := jsonRPCError(message, requestErr); response != nil {
				if _, err := output.Write(append(response, '\n')); err != nil {
					return err
				}
			}
			continue
		}
		for _, response := range responses {
			if _, err := output.Write(append(response, '\n')); err != nil {
				return err
			}
		}
	}
	return scanner.Err()
}

func (b bridge) forward(
	ctx context.Context, token string, message []byte, protocolVersion string,
) ([][]byte, error) {
	req, err := http.NewRequestWithContext(
		ctx, http.MethodPost, b.baseURL+"/mcp", bytes.NewReader(message),
	)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json, text/event-stream")
	req.Header.Set("Content-Type", "application/json")
	if protocolVersion != "" {
		req.Header.Set("MCP-Protocol-Version", protocolVersion)
	}
	response, err := b.client.Do(req)
	if err != nil {
		return nil, errors.New("Portfolio Analyser MCP server is not reachable")
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusAccepted || response.StatusCode == http.StatusNoContent {
		return nil, nil
	}
	if response.StatusCode == http.StatusUnauthorized {
		return nil, errors.New("Portfolio Analyser connection is missing or revoked; run portfolio-analyser-setup")
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, fmt.Errorf("Portfolio Analyser MCP server returned HTTP %d", response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxMessageSize+1))
	if err != nil {
		return nil, err
	}
	if len(body) > maxMessageSize {
		return nil, errors.New("Portfolio Analyser MCP response is too large")
	}
	if strings.HasPrefix(response.Header.Get("Content-Type"), "text/event-stream") {
		return parseSSE(body)
	}
	compact := &bytes.Buffer{}
	if err := json.Compact(compact, body); err != nil {
		return nil, errors.New("Portfolio Analyser MCP server returned invalid JSON")
	}
	return [][]byte{compact.Bytes()}, nil
}

func parseSSE(body []byte) ([][]byte, error) {
	var messages [][]byte
	var data []string
	flush := func() error {
		if len(data) == 0 {
			return nil
		}
		joined := []byte(strings.Join(data, "\n"))
		compact := &bytes.Buffer{}
		if err := json.Compact(compact, joined); err != nil {
			return errors.New("Portfolio Analyser MCP server returned invalid SSE data")
		}
		messages = append(messages, append([]byte(nil), compact.Bytes()...))
		data = nil
		return nil
	}
	scanner := bufio.NewScanner(bytes.NewReader(body))
	scanner.Buffer(make([]byte, 64*1024), maxMessageSize)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			if err := flush(); err != nil {
				return nil, err
			}
			continue
		}
		if strings.HasPrefix(line, "data:") {
			data = append(data, strings.TrimSpace(strings.TrimPrefix(line, "data:")))
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if err := flush(); err != nil {
		return nil, err
	}
	return messages, nil
}

func initializeProtocolVersion(message []byte) string {
	var request struct {
		Method string `json:"method"`
		Params struct {
			ProtocolVersion string `json:"protocolVersion"`
		} `json:"params"`
	}
	if json.Unmarshal(message, &request) != nil || request.Method != "initialize" {
		return ""
	}
	return request.Params.ProtocolVersion
}

func jsonRPCError(request []byte, requestErr error) []byte {
	var envelope struct {
		ID json.RawMessage `json:"id"`
	}
	if json.Unmarshal(request, &envelope) != nil || len(envelope.ID) == 0 {
		return nil
	}
	response, _ := json.Marshal(map[string]any{
		"jsonrpc": "2.0",
		"id":      envelope.ID,
		"error": map[string]any{
			"code":    -32000,
			"message": safeError(requestErr),
		},
	})
	return response
}

func keyringStorageError(err error) error {
	if errors.Is(err, keyring.ErrNotFound) {
		return errors.New("Portfolio Analyser is not paired; run portfolio-analyser-setup")
	}
	if runtime.GOOS == "linux" {
		return errors.New("secure Linux keyring unavailable; install and unlock a Secret Service such as GNOME Keyring")
	}
	return errors.New("the operating system credential store is unavailable")
}

func safeError(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

func fatal(message string) {
	_, _ = fmt.Fprintln(os.Stderr, message)
	os.Exit(1)
}
