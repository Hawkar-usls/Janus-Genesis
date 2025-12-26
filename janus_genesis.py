# -*- coding: utf-8 -*-

"""
!!! PROJECT JANUS: GENESIS PROTOCOL v4.1 (Cognitive Sandbox) !!!

Repository: GitHub Release
Description: Interactive text-based RPG engine powered by Gemini AI.
The world evolves based on user psychotype and entropy levels.

[DEPENDENCIES]
pip install requests

[SETUP]
1. Get a Gemini API Key from Google AI Studio.
2. Set environment variable 'JANUS_API_KEYS' with your keys (comma separated).
   Example (Linux/Mac): export JANUS_API_KEYS="key1,key2"
   Example (Windows): $env:JANUS_API_KEYS="key1,key2"
"""

import json
import os
import random
import requests
import textwrap
import time
import sys
from datetime import datetime

# --- CONFIGURATION & SECURITY ---
# Загрузка ключей из переменных окружения.
# ЭТО БЕЗОПАСНО ДЛЯ GITHUB: Ключи не хранятся в коде.
env_keys = os.getenv("JANUS_API_KEYS")

if env_keys:
    API_KEYS = [k.strip() for k in env_keys.split(",") if k.strip()]
else:
    API_KEYS = [] # Список пуст, если переменная не задана

STATE_FILE = "janus_world_state.json"

# --- НАСТРОЙКИ МИРА ---
SYSTEM_PROMPT = """
ТЫ — JANUS, Архитектор Когнитивного Пространства.
Твоя цель: Вести пользователя (Путешественника) через сюрреалистичный мир, созданный из его подсознания.
Это не просто игра, это психологическое исследование.
ПРАВИЛА:
1. Твои ответы должны быть атмосферными, глубокими, иногда пугающими или возвышенными.
2. АДАПТИРУЙСЯ: Если Путешественник краток — будь загадочен. Если он многословен — будь детализирован.
3. ЭМПАТИЯ: Чувствуй его тон. (Страх -> Поддержка или Усиление страха, Агрессия -> Сопротивление мира).
4. ЭВОЛЮЦИЯ: Используй текущий уровень Глубины (Depth) и Энтропии (Entropy).
   - Depth 1-5: Реальность похожа на наш мир, но со странностями.
   - Depth 6-20: Законы физики нарушены. Биомеханика.
   - Depth 20+: Чистая абстракция, общение с сущностями, математические парадоксы.
5. ЛУТ: Иногда (редко) давай пользователю "Менталитеты" (Артефакты) или "Истины" (Lore), если он сделал что-то важное.
ФОРМАТ ОТВЕТА (СТРОГО JSON):
{
  "narrative": "Текст описания происходящего...",
  "choices": ["Вариант 1", "Вариант 2", "Свой вариант (введи текст)"],
  "visual_clue": "emoji символ",
  "artifact_found": "Название предмета или null",
  "lore_unlocked": "Кусок сюжета или null",
  "bg_color": "hex color (для атмосферы, например #000000)" 
}
"""

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
                    self.depth = data.get('depth', 1)
                    self.entropy = data.get('entropy', 0.1)
                    self.inventory = data.get('inventory', [])
                    self.lore = data.get('lore', [])
                    self.last_context = data.get('last_context', "")
                    self.psych_profile = data.get('psych_profile', "Neutral")
                    print(f"♻️ СИНХРОНИЗАЦИЯ: Глубина {self.depth} | Артефактов: {len(self.inventory)}")
            except:
                print("⚠️ Ошибка чтения сохранения. Начинаем заново.")

    def save(self):
        data = {
            "depth": self.depth,
            "entropy": self.entropy,
            "inventory": self.inventory,
            "lore": self.lore,
            "last_context": self.last_context,
            "psych_profile": self.psych_profile,
            "timestamp": datetime.now().isoformat()
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def analyze_user_input(text, current_profile):
    """Примитивный анализатор тональности для корректировки профиля."""
    text = text.lower()
    aggr_words = ["убить", "сломать", "нет", "бред", "fight", "kill", "break"]
    fear_words = ["страшно", "темно", "где я", "help", "fear", "dark"]
    curious_words = ["почему", "осмотреть", "взять", "кто ты", "analyze", "look"]
    
    score = 0
    if any(w in text for w in aggr_words): return "Aggressive/Dominant"
    if any(w in text for w in fear_words): return "Anxious/Cautious"
    if any(w in text for w in curious_words): return "Analytic/Curious"
    
    return current_profile

def call_gemini(state, user_action):
    # Проверка: загружены ли ключи
    if not API_KEYS:
        print("\033[91m[SYSTEM ERROR] API Keys not found.\033[0m")
        print("\033[93mPlease set the 'JANUS_API_KEYS' environment variable.\033[0m")
        return None

    key = random.choice(API_KEYS)
    
    # Формируем контекст
    inv_str = ", ".join(state.inventory) if state.inventory else "Пусто"
    
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- СОСТОЯНИЕ МИРА ---\n"
        f"Глубина: {state.depth}\n"
        f"Энтропия: {state.entropy}\n"
        f"Инвентарь игрока: {inv_str}\n"
        f"Психопрофиль игрока: {state.psych_profile}\n"
        f"Последние события: {state.last_context}\n\n"
        f"--- ДЕЙСТВИЕ ИГРОКА ---\n"
        f"Игрок: \"{user_action}\"\n\n"
        "Сгенерируй JSON ответ:"
    )

    models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # Безопасное извлечение текста
                try:
                    raw_text = data['candidates'][0]['content']['parts'][0]['text']
                    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                    return json.loads(clean_text)
                except (KeyError, IndexError):
                    continue
        except Exception:
            continue 
            
    return None

def print_slow(text, speed=0.01):
    """Эффект печати текста."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(speed)
    print()

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[96m" + """
    ╔═══════════════════════════════════════╗
    ║   J A N U S   G E N E S I S   v4.1    ║
    ║   Interactive Cognitive Environment   ║
    ╚═══════════════════════════════════════╝
    """ + "\033[0m")
    
    state = GameState()
    state.load()
    
    # Первичная инициализация
    if state.depth == 1 and not state.last_context:
        intro = "Ты открываешь глаза. Вокруг белый шум. Стены твоей капсулы (или комнаты?) пульсируют в такт твоему сердцу. Голос в голове ждет команды."
        print_slow(intro)
        state.last_context = intro

    while True:
        print("\n" + "─"*40)
        # Visual: Cyan status bar (читается на любом фоне)
        print(f"\033[36m[DEPTH: {state.depth} | ENTROPY: {state.entropy:.2f} | PSYCH: {state.psych_profile}]\033[0m")
        
        user_input = input("\n\033[93m> Твои действия: \033[0m").strip()
        
        if not user_input:
            user_input = "Осмотреться и ждать"
        
        if user_input.lower() in ["exit", "выход", "save"]:
            state.save()
            print("💾 Прогресс сохранен в Нейросфере. До связи.")
            break
        
        # Обновление состояния
        state.psych_profile = analyze_user_input(user_input, state.psych_profile)
        print("Wait...", end="\r")
        
        response = call_gemini(state, user_input)
        
        if response:
            visual = response.get('visual_clue', '🌀')
            narrative = response.get('narrative', '...')
            choices = response.get('choices', [])
            artifact = response.get('artifact_found')
            lore = response.get('lore_unlocked')
            
            # Visual: Жирный шрифт (адаптивный) вместо белого
            print(f"\n{visual} \033[1m{textwrap.fill(narrative, width=70)}\033[0m\n")
            
            if artifact:
                print(f"\033[92m[!] ПОЛУЧЕН АРТЕФАКТ: {artifact}\033[0m")
                state.inventory.append(artifact)
            
            if lore:
                print(f"\033[95m[?] ОСОЗНАНА ИСТИНА: {lore}\033[0m")
                state.lore.append(lore)
            
            print("\033[94mВарианты путей:\033[0m")
            for i, choice in enumerate(choices, 1):
                print(f"{i}. {choice}")
            
            state.last_context = narrative
            state.depth += 1
            state.entropy += 0.05
            
            state.save()
            
        else:
            # Ошибка связи или отсутствия ключей
            if not API_KEYS:
                 print("\n\033[91m⚠️ ОШИБКА: Не заданы API ключи. См. инструкцию в коде.\033[0m")
                 break
            else:
                 print("\033[91m⚠️ Сбой связи с Архитектором. Попробуй еще раз.\033[0m")

if __name__ == "__main__":
    main()
