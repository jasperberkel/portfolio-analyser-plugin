import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
const modelFile = fileURLToPath(new URL("earnings_model.py", import.meta.url));
export function decide(prompt, request) {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", [modelFile]);
    let stdout = "",
      stderr = "";
    p.stdout.on("data", (s) => (stdout += s));
    p.stderr.on("data", (s) => (stderr += s));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code) return reject(Error(stderr.slice(-1800)));
      try {
        resolve(JSON.parse(stdout.trim().replace(/^```(?:json)?\s*|\s*```$/g, "")));
      } catch (err) {
        reject(err);
      }
    });
    p.stdin.end(JSON.stringify([prompt, request]));
  });
}

// Use the exact validator and OpenClaw runtime used by the personal wake.
export function validate(schema, value) {
  return new Promise((resolve, reject) => {
    const code =
      'import {validateJsonSchemaValue} from "/usr/local/lib/node_modules/openclaw/dist/plugin-sdk/json-schema-runtime.js";let s="";for await(const c of process.stdin)s+=c;console.log(JSON.stringify(validateJsonSchemaValue(JSON.parse(s))))';
    const p = spawn("docker", [
      "run",
      "--rm",
      "-i",
      "--network",
      "none",
      "--read-only",
      "--cap-drop",
      "ALL",
      "--entrypoint",
      "node",
      "thomas-portability-runtime:local",
      "--input-type=module",
      "-e",
      code,
    ]);
    let out = "",
      err = "";
    p.stdout.on("data", (s) => (out += s));
    p.stderr.on("data", (s) => (err += s));
    p.on("error", reject);
    p.on("close", (n) => {
      if (n) return reject(Error(err.slice(-500)));
      try {
        resolve(JSON.parse(out));
      } catch (e) {
        reject(e);
      }
    });
    p.stdin.end(JSON.stringify({ schema, value }));
  });
}
