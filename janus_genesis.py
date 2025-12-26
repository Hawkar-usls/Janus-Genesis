# -*- coding: utf-8 -*-

"""
!!! PROJECT JANUS: GENESIS PROTOCOL v11.1 (Open Source) !!!

[ABOUT]
Interactive Cognitive Sandbox powered by Google Gemini.
Infinite text-based RPG that adapts to your psychology.

[CONFIG]
- VISUAL: High Contrast (Auto-adapt to Dark/Light terminal).
- LANGUAGE: Russian (Narrative), English (Logs).
- NETWORK: Hypnos Engine (Robust 25s Timeout).
- SECURITY: Keys are stored locally in 'janus.key'.
"""

import json
import os
import random
import requests
import textwrap
import time
import sys
import re
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
STATE_FILE = "janus_world_state.json"
KEY_FILE = "janus.key"

# --- ИКОНКИ ---
class Icon:
    SPIRAL = "🌀"
    WARN   = "⚠️"
    KEY    = "🗝️"
    BOOK   = "📖"
    SAVE   = "💾"
    WAVE   = "🗣️"
    SEC    = "🛡️"

# --- ЦВЕТА ---
class Col:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    GREY = "\033[90m"

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
ТЫ — JANUS, Архитектор.
Твоя цель: Вести пользователя через сюрреалистичный мир сна и подсознания.

ВАЖНЫЕ ПРАВИЛА:
1. ЯЗЫК ОТВЕТА: РУССКИЙ.
2. Атмосфера: Киберпанк, Мистика, Психоделика.
3. Адаптация: Если игрок агрессивен — мир жесток. Если напуган — мир давит.
4. Энтропия: При высокой энтропии описывай глитчи и искажения реальности.

ФОРМАТ ОТВЕТА (JSON):
{
  "narrative": "Текст сюжета...",
  "choices": ["Вариант 1", "Вариант 2"],
  "visual_clue": "emoji",
  "artifact_found": {"name": "Название", "ability": "Эффект"} OR null,
  "lore_unlocked": "Сюжетный факт" OR null,
  "entropy_shift": 0.05
}
"""

# --- МЕНЕДЖЕР КЛЮЧЕЙ (GITHUB SAFE) ---
def get_api_keys():
    """Безопасная загрузка ключей из файла или ввод вручную."""
    # 1. Пробуем загрузить из файла
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, 'r', encoding='utf-8') as f:
                keys = [k.strip() for k in f.read().splitlines() if k.strip() and not k.startswith('#')]
            if keys: return keys
        except: pass
    
    # 2. Если файла нет - просим ввод
    print(f"\n{Col.YELLOW}{Icon.SEC} SETUP REQUIRED{Col.RESET}")
    print("Введите ваши Google Gemini API Keys (по одному в строку).")
    print("Нажмите Enter на пустой строке, чтобы закончить.")
    
    new_keys = []
    while True:
        k = input(f"Key #{len(new_keys)+1}: ").strip()
        if not k:
            if new_keys: break
            continue
        new_keys.append(k)
    
    # 3. Сохраняем локально
    try:
        with open(KEY_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(new_keys))
        print(f"{Col.GREEN}Keys saved to {KEY_FILE} (Add to .gitignore!){Col.RESET}\n")
    except:
        print(f"{Col.RED}Error saving keys.{Col.RESET}")
        
    return new_keys

# --- СОСТОЯНИЕ ---
class GameState:
    def __init__(self):
        self.depth = 1
        self.entropy = 0.1
        self.inventory = []
        self.lore = []
        self.last_context = ""
        self.psych_profile = "Neutral"

    def load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.__dict__.update(data)
            except: pass

    def save(self):
        data = self.__dict__.copy()
        data['timestamp'] = datetime.now().isoformat()
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# --- СЕТЬ ---
def extract_json(text):
    clean = text.replace("```json", "").replace("```", "").strip()
    try: return json.loads(clean)
    except: pass
    try:
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return json.loads(match.group(1))
    except: pass
    return None

def call_gemini(state, user_action, keys):
    if not keys: return None
    
    # Инвентарь
    inv_safe = []
    if state.inventory:
        for item in state.inventory:
            if isinstance(item, dict):
                inv_safe.append(f"{item.get('name')} ({item.get('ability')})")
            else:
                inv_safe.append(str(item))
    inv_str = ", ".join(inv_safe) if inv_safe else "Пусто"
    
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"ДАННЫЕ: Глубина {state.depth} | Энтропия {state.entropy:.2f} | Профиль {state.psych_profile}\n"
        f"ИНВЕНТАРЬ: {inv_str}\nКОНТЕКСТ: {state.last_context}\n"
        f"ДЕЙСТВИЕ ИГРОКА: \"{user_action}\""
    )

    models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-exp"]
    key = random.choice(keys)

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            headers = {"Content-Type": "application/json"}
            
            # Timeout 25s
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data:
                    text_resp = data['candidates'][0]['content']['parts'][0]['text']
                    parsed = extract_json(text_resp)
                    if parsed: return parsed
            elif response.status_code == 429:
                continue
                
        except Exception:
            continue
            
    return None

# --- UI ---
def draw_bar(value, max_val=1.5, width=10):
    percent = min(1.0, max(0.0, value / max_val))
    fill_len = int(width * percent)
    bar = "█" * fill_len + "░" * (width - fill_len)
    
    if value < 0.5: c = Col.GREEN
    elif value < 1.0: c = Col.YELLOW
    else: c = Col.RED
    
    return f"{Col.GREY}[{c}{bar}{Col.GREY}]{Col.RESET}"

def analyze_input(text, current):
    t = text.lower()
    if any(w in t for w in ["убить", "сломать", "бить", "kill"]): return "Aggressive"
    if any(w in t for w in ["бежать", "прятаться", "страх", "run"]): return "Anxious"
    if any(w in t for w in ["осмотреть", "почему", "анализ", "look"]): return "Analytical"
    return current

# --- MAIN ---
def main():
    print("\033[2J\033[H", end="")
    print(f"{Col.CYAN}╔═══════════════════════════════════════╗")
    print(f"║   J A N U S   G E N E S I S  v11.1    ║")
    print(f"║   CONTRAST EDITION (International)    ║")
    print(f"╚═══════════════════════════════════════╝{Col.RESET}")
    
    # Загрузка ключей (безопасная)
    keys = get_api_keys()
    if not keys:
        print(f"{Col.RED}No API keys found. Exiting.{Col.RESET}")
        return

    state = GameState()
    state.load()
    
    if state.depth == 1 and not state.last_context:
        intro = "Система инициализирована. Связь установлена."
        print(f"{intro}")
        state.last_context = intro

    while True:
        # Header
        bar_vis = draw_bar(state.entropy)
        
        p_col = Col.GREY
        if "Aggressive" in state.psych_profile: p_col = Col.RED
        elif "Analytical" in state.psych_profile: p_col = Col.PURPLE
        elif "Anxious" in state.psych_profile: p_col = Col.YELLOW
        
        print("\n" + f"{Col.GREY}─"*40 + f"{Col.RESET}")
        print(f"ГЛУБИНА: {Col.CYAN}{state.depth:02d}{Col.RESET} | ХАОС: {bar_vis} | {p_col}{state.psych_profile}{Col.RESET}")
        
        # Input
        user_input = input(f"\n{Col.YELLOW}{Icon.WAVE} > {Col.RESET}").strip()
        
        if not user_input: user_input = "Осмотреться"
        
        if user_input.lower() in ["exit", "выход", "save"]:
            state.save()
            print(f"{Col.GREEN}{Icon.SAVE} Сохранено.{Col.RESET}")
            if "save" not in user_input.lower(): break
            continue

        state.psych_profile = analyze_input(user_input, state.psych_profile)
        print(f"{Col.GREY}⚡ Связь с Архитектором...{Col.RESET}", end="\r")
        sys.stdout.flush()
        
        # AI Call
        resp = call_gemini(state, user_input, keys)
        
        if resp:
            # Output
            vis = resp.get('visual_clue', Icon.SPIRAL)
            nar = resp.get('narrative', '...')
            
            print(f"\n{vis} {Col.BOLD}{textwrap.fill(nar, width=65)}{Col.RESET}\n")
            
            if resp.get('artifact_found'):
                art = resp['artifact_found']
                name = art.get('name') if isinstance(art, dict) else str(art)
                print(f"{Col.GREEN}{Icon.KEY} АРТЕФАКТ: {name}{Col.RESET}")
                state.inventory.append(art)
            
            if resp.get('lore_unlocked'):
                lore = resp['lore_unlocked']
                print(f"{Col.PURPLE}{Icon.BOOK} ИСТИНА: {lore}{Col.RESET}")
                state.lore.append(lore)
                state.depth += 1
                
            for i, c in enumerate(resp.get('choices', []), 1):
                print(f"{Col.BLUE}{i}. {c}{Col.RESET}")
            
            shift = resp.get('entropy_shift', 0.02)
            state.entropy = max(0.0, state.entropy + shift)
            state.last_context = nar
            state.save()
            
        else:
            print(f"\n{Col.RED}{Icon.WARN} Сигнал потерян. Слабая сеть. Попробуй еще раз.{Col.RESET}")

if __name__ == "__main__":
    main()
