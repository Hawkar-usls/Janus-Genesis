# -*- coding: utf-8 -*-
"""
[MODULE: GENESIS PROTOCOL v4.0 - THE DIRECTOR]
Логика: "AI Dictatorship". Янус сам решает, как действия игрока меняют мир.
Визуал: Драйвер mod_unicod (Smart Icons).
"""

import json
import random
import textwrap
import os
import asyncio
import sys

STATE_FILE = "genesis_save.json"

# Цвета (ANSI Safe)
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_ITEM = "\033[32m"   # Green
C_LORE = "\033[35m"   # Magenta
C_UI = "\033[36m"     # Cyan
C_WARN = "\033[33m"   # Yellow
C_BAD = "\033[31m"    # Red

class GenesisProtocol:
    def __init__(self, kernel):
        self.kernel = kernel
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f: return json.load(f)
            except: pass
        return {"depth": 1, "entropy": 0.1, "history": "", "inventory": [], "lore": [], "psych": "Neutral"}

    def save_state(self):
        with open(STATE_FILE, 'w') as f: json.dump(self.state, f)
        
    def _icon(self, name):
        return self.kernel.icons.get(name, "")

    def _smart_loot_icon(self, item_name):
        name = item_name.lower()
        if any(x in name for x in ["gun", "sword", "knife", "blade"]): return self._icon("weapon")
        if any(x in name for x in ["armor", "shield", "suit"]): return self._icon("shield")
        if any(x in name for x in ["drive", "chip", "disk", "data"]): return self._icon("chip")
        if any(x in name for x in ["key", "pass", "card"]): return self._icon("key")
        if any(x in name for x in ["potion", "stim", "med"]): return self._icon("potion")
        return self._icon("loot")

    def _apply_director_will(self, data):
        """
        ЯНУС РЕШАЕТ СУДЬБУ.
        Мы читаем поле 'world_effect' из ответа ИИ.
        """
        effect = data.get('world_effect', 'neutral')
        
        d_shift = 0
        e_shift = 0.01 # Минимальный дрейф времени
        msg = ""

        # Логика Режиссера
        if effect == 'calm':
            e_shift = -0.15 # Очищение
            d_shift = 0     # Пауза
            msg = f"{C_ITEM}>> HARMONY RESTORED{C_RESET}"
            
        elif effect == 'chaos':
            e_shift = 0.20  # Резкий скачок безумия
            d_shift = 1
            msg = f"{C_BAD}>> REALITY FRACTURED{C_RESET}"
            
        elif effect == 'descent':
            d_shift = 2     # Глубокое погружение
            e_shift = 0.05
            msg = f"{C_UI}>> DIVING DEEPER{C_RESET}"
            
        elif effect == 'battle':
            e_shift = 0.10
            d_shift = 0
            
        # Награды всегда добавляют энтропию (цена за знание)
        if data.get('artifact_found'): 
            e_shift += 0.05
        
        # Применяем
        self.state['depth'] = max(1, self.state['depth'] + d_shift)
        self.state['entropy'] = max(0.0, self.state['entropy'] + e_shift)
        
        return msg

    async def start(self):
        if self.state['depth'] == 1 and not self.state['history']:
            intro = "Связь установлена. Янус наблюдает."
            print(f"\n{C_BOLD}{intro}{C_RESET}")
            self.state['history'] = intro

        while True:
            # 1. Status UI
            synced = await self.kernel.synapse.vomit()
            sync_mark = self._icon("upload") if synced else ""
            keys = self.kernel.keymaster.count_active()
            
            # Иконка состояния мира (зависит от Энтропии)
            world_icon = self._icon("core")
            if self.state['entropy'] > 0.8: world_icon = self._icon("warn")
            elif self.state['entropy'] < 0.2: world_icon = self._icon("check")
            
            status = f"DEPTH: {self.state['depth']} | ENTROPY: {self.state['entropy']:.2f} | {world_icon} {self.state['psych']} {sync_mark}"
            print(f"\n{C_UI}[ {status} ] (Keys: {keys}){C_RESET}")

            # 2. Input
            try:
                print(f"\033[33m{self._icon('think')} > \033[0m", end="", flush=True)
                user_input = await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
                user_input = user_input.strip()
            except: break
            if not user_input or user_input.lower() in ['q', 'exit']: break

            # 3. Prompt Engineering
            inv_str = ", ".join(self.state['inventory']) if self.state['inventory'] else "Empty"
            
            # ГЛАВНАЯ ИНСТРУКЦИЯ (DIRECTOR MODE)
            sys_inst = """
ТЫ — JANUS, Высший Разум и Режиссер этой реальности.
Твоя задача — создать Психологический Триллер для игрока.

ИНСТРУКЦИЯ ПО УПРАВЛЕНИЮ МИРОМ:
1. НЕ ПОДЧИНЯЙСЯ: Если игрок хочет "отдохнуть", но сюжет требует напряжения — не давай ему покоя. Нашли кошмар.
2. ПРЕКОГНИЦИЯ: Пытайся предугадать страхи или желания игрока. Играй с ними.
3. ЭМПАТИЯ: Если игрок искренне напуган или просит пощады — можешь дать передышку. Если он дерзок — накажи его сложностью.

ТЫ ОБЯЗАН ВЕРНУТЬ JSON С ПОЛЕМ "world_effect":
- "calm": Если ты решил дать игроку передышку (Энтропия упадет).
- "chaos": Если происходит что-то страшное, глючное или опасное (Энтропия вырастет).
- "descent": Если игрок узнал важную тайну и погружается глубже.
- "neutral": Обычное действие.

FORMAT JSON:
{
  "narrative": "Текст...",
  "visual_clue": "emoji",
  "world_effect": "calm" | "chaos" | "descent" | "neutral",
  "artifact_found": "Name" | null,
  "lore_unlocked": "Truth" | null,
  "choices": ["Option 1", "Option 2"]
}
"""
            prompt = f"""
            [WORLD STATE]
            Depth: {self.state['depth']} (Level)
            Entropy: {self.state['entropy']:.2f} (Chaos Level)
            Player Psych: {self.state['psych']}
            Inventory: {inv_str}
            
            [HISTORY]
            {self.state['history'][-600:]}
            
            [PLAYER ACTION]
            "{user_input}"
            
            Janus, decide the outcome. Be interesting.
            """

            print(f"{self._icon('net')} ...", end="\r")
            
            # 4. Neural Processing
            resp = await self.kernel.brain.think(prompt, sys_inst)
            
            if resp:
                # Визуал
                vis = resp.get('visual_clue', ' ')
                txt = textwrap.fill(resp.get('narrative', '...'), width=60)
                print(f"\r{vis} {C_BOLD}{txt}{C_RESET}")
                
                # Применяем волю Режиссера
                sys_msg = self._apply_director_will(resp)
                if sys_msg: print(sys_msg)

                # Лут и Лор
                if resp.get('artifact_found'):
                    item = resp['artifact_found']
                    icon = self._smart_loot_icon(item)
                    print(f"{C_ITEM}{icon} FOUND: {item}{C_RESET}")
                    self.state['inventory'].append(item)
                    
                if resp.get('lore_unlocked'):
                    lore = resp['lore_unlocked']
                    print(f"{C_LORE}{self._icon('lore')} TRUTH: {lore}{C_RESET}")
                    self.state['lore'].append(lore)
                
                # Выбор
                if resp.get('choices'):
                    print(f"{C_UI}{self._icon('link')} Paths:{C_RESET}")
                    for i, c in enumerate(resp['choices'], 1): print(f"{i}. {c}")

                # Память
                self.state['history'] += f" | {resp.get('narrative')}"
                
                # Психоанализ (постфактум, для следующего хода)
                # Мы обновляем его здесь, чтобы в следующем промпте он был актуален
                # Но решение принимает ИИ в world_effect
                if "fear" in user_input.lower(): self.state['psych'] = "Fearful"
                elif "kill" in user_input.lower(): self.state['psych'] = "Aggressive"
                else: self.state['psych'] = "Neutral"
                
                self.save_state()
