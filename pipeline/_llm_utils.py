"""
Shared LLM utility — cascade: Groq → Gemini → Ollama
Imported by all pipeline modules
"""
import os
from typing import Optional
from utils.logger import get_logger
from utils.rate_limiter import get_limiter

log = get_logger("llm_utils")
limiter = get_limiter()


def call_groq(prompt: str, system: str = "", temperature: float = 0.8) -> Optional[str]:
    if not limiter.acquire("groq"):
        return None
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature,
            max_tokens=2048
        )
        return resp.choices[0].message.content
    except Exception as e:
        log.warning(f"Groq error: {e}")
        return None


def call_gemini(prompt: str, system: str = "") -> Optional[str]:
    if not limiter.acquire("gemini"):
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")
        full = f"{system}\n\n{prompt}" if system else prompt
        resp = model.generate_content(full)
        return resp.text
    except Exception as e:
        log.warning(f"Gemini error: {e}")
        return None


def call_ollama(prompt: str, system: str = "") -> Optional[str]:
    try:
        import requests
        payload = {
            "model": "llama3.2",
            "prompt": f"{system}\n\n{prompt}" if system else prompt,
            "stream": False
        }
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        if r.ok:
            return r.json().get("response", "")
    except Exception as e:
        log.warning(f"Ollama error: {e}")
    return None


def llm(prompt: str, system: str = "", temperature: float = 0.8) -> str:
    """LLM cascade: Groq → Gemini → Ollama"""
    for fn, name in [(call_groq, "Groq"), (call_gemini, "Gemini"), (call_ollama, "Ollama")]:
        if name == "Groq":
            result = fn(prompt, system, temperature)
        else:
            result = fn(prompt, system)
        if result:
            log.debug(f"LLM used: {name}")
            return result
    log.error("ALL LLMs FAILED")
    return ""


def parse_json_response(raw: str) -> dict | list:
    """Parse JSON from LLM — strips markdown code fences"""
    import json
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()
    return json.loads(raw)
