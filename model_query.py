#! /usr/bin/env python3

import json
import os

import requests


BASE_URL = os.environ.get("LLM_PERF_BASE_URL", "http://172.28.22.23:8888").rstrip("/")
MESSAGES_URL = BASE_URL + "/v1/messages"
CHAT_COMPLETIONS_URL = BASE_URL + "/v1/chat/completions"
MODEL_NAME = os.environ.get("LLM_PERF_MODEL", "qwen")
API_KEY = os.environ.get("LLM_PERF_API_KEY", "EMPTY")
TEMPERATURE = float(os.environ.get("LLM_PERF_TEMPERATURE", "0.0"))
TOP_P = float(os.environ.get("LLM_PERF_TOP_P", "1.0"))
CONNECT_TIMEOUT = float(os.environ.get("LLM_PERF_CONNECT_TIMEOUT", "10"))
READ_TIMEOUT = float(os.environ.get("LLM_PERF_READ_TIMEOUT", "600"))
MAX_TOKENS_CAP = int(os.environ.get("LLM_PERF_MAX_TOKENS_CAP", "0"))


class FailedQueryError(Exception):
    def get_err_msg(self):
        return str(self)


def prepare_messages(prompt):
    try:
        parsed = json.loads(prompt)
        if isinstance(parsed, list) and all(
            isinstance(msg, dict) and "role" in msg and "content" in msg for msg in parsed
        ):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return [{"role": "user", "content": prompt}]


def build_messages_payload(messages, max_resp_tokens):
    system_parts = []
    normal_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system_parts.append(content)
            continue
        normal_messages.append({"role": role, "content": content})

    payload = {
        "model": MODEL_NAME,
        "messages": normal_messages,
        "stream": True,
        "max_tokens": max_resp_tokens,
    }
    if system_parts:
        payload["system"] = "\n".join(system_parts)
    return payload


def build_chat_completions_payload(messages, max_resp_tokens):
    return {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "max_tokens": max_resp_tokens,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
    }


def iter_messages_stream(response):
    for line in response.iter_lines(chunk_size=128, decode_unicode=False):
        if not line or not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if not data or data == b"[DONE]":
            continue
        try:
            line_json = json.loads(data)
        except json.JSONDecodeError:
            continue

        event_type = line_json.get("type")
        if event_type == "content_block_delta":
            delta = line_json.get("delta") or {}
            token_text = delta.get("text")
            if token_text:
                yield token_text
        elif event_type == "message_delta":
            delta = line_json.get("delta") or {}
            token_text = delta.get("text")
            if token_text:
                yield token_text


def iter_chat_completions_stream(response):
    for line in response.iter_lines(chunk_size=128, decode_unicode=False):
        if not line or not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if not data or data == b"[DONE]":
            continue
        try:
            line_json = json.loads(data)
        except json.JSONDecodeError:
            continue

        for choice in line_json.get("choices") or []:
            delta = choice.get("delta") or {}
            token_text = delta.get("content")
            if token_text:
                yield token_text


def post_stream(url, payload, headers):
    return requests.post(
        url,
        headers=headers,
        json=payload,
        stream=True,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )


def try_messages_api(messages, max_resp_tokens, headers):
    payload = build_messages_payload(messages, max_resp_tokens)
    response = post_stream(MESSAGES_URL, payload, headers)
    if response.status_code == 200:
        return response, iter_messages_stream
    body = response.text[:1000]
    response.close()
    if response.status_code in {404, 405, 400, 415, 422, 500, 501}:
        return None, body
    raise FailedQueryError(f"http {response.status_code}: {body}")


def try_chat_completions_api(messages, max_resp_tokens, headers):
    payload = build_chat_completions_payload(messages, max_resp_tokens)
    response = post_stream(CHAT_COMPLETIONS_URL, payload, headers)
    if response.status_code == 200:
        return response, iter_chat_completions_stream
    body = response.text[:1000]
    response.close()
    raise FailedQueryError(f"http {response.status_code}: {body}")


def query_model(prompt, max_resp_tokens):
    if MAX_TOKENS_CAP > 0:
        max_resp_tokens = min(max_resp_tokens, MAX_TOKENS_CAP)
    messages = prepare_messages(prompt)
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }

    try:
        response, stream_iter = try_messages_api(messages, max_resp_tokens, headers)
        if response is None:
            response, stream_iter = try_chat_completions_api(messages, max_resp_tokens, headers)

        with response:
            for token_text in stream_iter(response):
                yield token_text
    except requests.RequestException as exc:
        raise FailedQueryError(str(exc))


if __name__ == "__main__":
    print("Use $python3 executor.py to test your query_model function")
