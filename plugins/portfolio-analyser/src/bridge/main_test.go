package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type memoryStore struct {
	token string
	err   error
}

func (s *memoryStore) Get() (string, error) {
	if s.err != nil {
		return "", s.err
	}
	if s.token == "" {
		return "", errors.New("not found")
	}
	return s.token, nil
}

func (s *memoryStore) Set(token string) error {
	s.token = token
	return s.err
}

func TestPairStoresTokenWithoutPrintingIt(t *testing.T) {
	store := &memoryStore{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/mcp/pairings/exchange" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"token":"top-secret","client_id":"00000000-0000-0000-0000-000000000001"}`)
	}))
	defer server.Close()

	b := bridge{baseURL: server.URL, store: store, client: server.Client()}
	output := &bytes.Buffer{}
	err := runPairCommand(b, []string{"--client", "Codex", "--platform", "macOS"}, strings.NewReader("AAAA-BBBB-CCCC\n"), output)
	if err != nil {
		t.Fatal(err)
	}
	if store.token != "top-secret" {
		t.Fatal("token was not stored")
	}
	if strings.Contains(output.String(), store.token) {
		t.Fatal("token was written to stdout")
	}
}

func TestForwardAddsAuthorizationAndCompactsResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer stored-token" {
			t.Fatal("missing bearer token")
		}
		if r.Header.Get("MCP-Protocol-Version") != "2025-06-18" {
			t.Fatal("missing protocol version")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, "{\n  \"jsonrpc\": \"2.0\", \"id\": 1, \"result\": {}\n}")
	}))
	defer server.Close()

	b := bridge{baseURL: server.URL, store: &memoryStore{token: "stored-token"}, client: server.Client()}
	responses, err := b.forward(context.Background(), "stored-token", []byte(`{"jsonrpc":"2.0","id":1}`), "2025-06-18")
	if err != nil {
		t.Fatal(err)
	}
	if len(responses) != 1 || !json.Valid(responses[0]) || bytes.Contains(responses[0], []byte("\n")) {
		t.Fatalf("unexpected response %q", responses)
	}
}

func TestServeReturnsSafeJSONRPCError(t *testing.T) {
	store := &memoryStore{token: "stored-token"}
	b := bridge{
		baseURL: "http://127.0.0.1:1",
		store:   store,
		client:  &http.Client{},
	}
	output := &bytes.Buffer{}
	err := b.serve(context.Background(), strings.NewReader(`{"jsonrpc":"2.0","id":7,"method":"tools/list"}`+"\n"), output)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(output.String(), `"code":-32000`) || strings.Contains(output.String(), store.token) {
		t.Fatalf("unexpected error response %s", output.String())
	}
}

func TestParseSSE(t *testing.T) {
	messages, err := parseSSE([]byte("event: message\ndata: {\"jsonrpc\":\"2.0\",\ndata: \"id\":1}\n\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(messages) != 1 || !json.Valid(messages[0]) {
		t.Fatalf("unexpected messages %q", messages)
	}
}
