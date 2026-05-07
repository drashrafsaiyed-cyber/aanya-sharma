"""
AANYA SHARMA — First-Time Setup Script
Run this ONCE to configure your system.
python setup.py
"""
import os
import sys
import json
import shutil
from pathlib import Path


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║         AANYA SHARMA — AI Influencer Setup               ║
║         Motivational / Mindset / Indian Audience         ║
╚══════════════════════════════════════════════════════════╝
    """)


def check_python():
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")


def create_env():
    if Path(".env").exists():
        print("✅ .env already exists")
        return
    shutil.copy(".env.example", ".env")
    print("✅ .env created from template")
    print("   ⚠️  IMPORTANT: Edit .env and add your API keys before running")


def create_dirs():
    dirs = [
        "output/images", "output/videos", "output/captions",
        "data/trends", "data/content_queue", "data/analytics",
        "character/reference_images", "character/lora_weights",
        "logs"
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✅ Directories created")


def check_comfyui():
    try:
        import requests
        resp = requests.get("http://127.0.0.1:8188/system_stats", timeout=2)
        if resp.ok:
            print("✅ ComfyUI running at localhost:8188")
            return True
    except:
        pass
    print("⚠️  ComfyUI NOT running — images will use HuggingFace/Pollinations fallback")
    print("   To enable ComfyUI:")
    print("   1. Download: https://github.com/comfyanonymous/ComfyUI")
    print("   2. Install models: Realistic Vision V6 or FLUX.1")
    print("   3. Run: python main.py")
    return False


def check_api_keys():
    from dotenv import load_dotenv
    load_dotenv()

    checks = {
        "GROQ_API_KEY": ("Groq", "groq.com → free, required for content generation"),
        "GEMINI_API_KEY": ("Gemini", "aistudio.google.com → free fallback LLM"),
        "INSTAGRAM_ACCESS_TOKEN": ("Instagram", "developers.facebook.com → required for posting"),
        "INSTAGRAM_ACCOUNT_ID": ("Instagram Account ID", "from Facebook Graph API Explorer"),
        "YOUTUBE_API_KEY": ("YouTube", "console.cloud.google.com → free 10K units/day"),
    }

    print("\n📋 API Key Status:")
    all_ok = True
    for env_var, (name, note) in checks.items():
        val = os.getenv(env_var, "")
        if val and val != f"your_{env_var.lower()}_here":
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} — {note}")
            all_ok = False

    optional = {
        "HF_TOKEN": "HuggingFace (optional but recommended)",
        "REDDIT_CLIENT_ID": "Reddit (optional, for trend research)",
        "GDRIVE_FOLDER_ID": "Google Drive (optional, for cloud storage)",
    }
    print("\n📋 Optional Keys:")
    for env_var, note in optional.items():
        val = os.getenv(env_var, "")
        status = "✅" if val else "⚠️ "
        print(f"  {status} {note}")

    return all_ok


def check_ollama():
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.ok:
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"✅ Ollama running with models: {', '.join(models) or 'none'}")
            if not models:
                print("   Run: ollama pull llama3.2")
    except:
        print("ℹ️  Ollama not running (optional local LLM)")
        print("   Install: https://ollama.ai — then: ollama pull llama3.2")


def install_deps():
    print("\n📦 Installing Python dependencies...")
    os.system(f"{sys.executable} -m pip install -r requirements.txt -q")
    print("✅ Dependencies installed")


def show_next_steps():
    print("""
╔══════════════════════════════════════════════════════════╗
║                    NEXT STEPS                            ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. 📝 Edit .env — add your API keys                     ║
║                                                          ║
║  2. 🖼️  Train Aanya's LoRA (optional but recommended):   ║
║     - Add 20-30 generated reference images to:          ║
║       character/reference_images/                        ║
║     - Use Kohya_ss or Automatic1111 DreamBooth           ║
║     - Save as: character/lora_weights/aanya_v1.safetensors║
║                                                          ║
║  3. 🚀 Test the pipeline:                                 ║
║     python orchestrator.py --status                      ║
║     python pipeline/trend_scraper.py                     ║
║     python pipeline/content_ideator.py                   ║
║                                                          ║
║  4. 🤖 Run first full pipeline:                           ║
║     python orchestrator.py                               ║
║                                                          ║
║  5. ⚙️  Set up GitHub Actions:                            ║
║     - Push to GitHub                                     ║
║     - Add secrets in: Settings → Secrets → Actions       ║
║     - Pipeline runs daily at 6:00 AM IST automatically   ║
║                                                          ║
║  6. 📱 Instagram Setup:                                   ║
║     - Convert to Professional/Creator account            ║
║     - Connect to Facebook Page                           ║
║     - Get access token via Graph API Explorer            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    print_banner()
    check_python()
    install_deps()
    create_dirs()
    create_env()
    check_api_keys()
    check_comfyui()
    check_ollama()
    show_next_steps()
