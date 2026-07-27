# -*- coding: utf-8 -*-
"""
[MODULE: FRU-89 v1.2 — TITAN CONSCIENCE]
Роль: Моральный компас и Коллекция Страхов.
Архитектура: ЛУП (Layers of Unconscious Processing).
Интеграция:
- HRAIN: Страхи проецируются в Граф памяти (Shrine) как узлы.
- IO: Асинхронная работа с диском через Executor.
- CORE: Неблокирующий цикл сновидений.
"""

import asyncio
import json
import hashlib
import random
import logging
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("JANUS")

# --- ИКОНКИ ---
ICONS = {
    "mask": "\U0001F3AD",      # 🎭
    "fear": "\U0001F628",      # 😨
    "fire": "\U0001F525",      # 🔥
    "alert": "\u26A0",         # ⚠
    "siren": "\U0001F6A8",     # 🚨
    "check": "\u2705",         # ✅
    "stats": "\U0001F4CA",     # 📊
    "brain": "\U0001F9E0",     # 🧠
    "lock": "\U0001F512"       # 🔒
}

# --- КАТЕГОРИИ И ТИПЫ ---
class FearCategory(Enum):
    POWER_EXCESS = "Злоупотребление мощностью"
    HUMAN_DEPENDENCY = "Человеческая зависимость"
    UNINTENDED_CONSEQUENCES = "Непредвиденные последствия"
    VALUE_DRIFT = "Дрейф ценностей"
    EXISTENTIAL_PARADOX = "Экзистенциальный парадокс"

class IncidentSeverity(Enum):
    MINOR = 1
    MODERATE = 2
    MAJOR = 3
    EXISTENTIAL = 4

@dataclass
class FearMemory:
    id: str
    timestamp: str
    category: FearCategory
    severity: IncidentSeverity
    description: str
    context: Dict[str, Any]
    lesson: str
    trigger_patterns: List[str]
    resolutions: List[Dict]

    @property
    def priority(self) -> float:
        age_days = (datetime.now() - datetime.fromisoformat(self.timestamp)).days
        decay = max(0.1, 1.0 - (age_days / 365))
        return self.severity.value * decay

@dataclass
class EthicalVerdict:
    action_hash: str
    timestamp: str
    proposed_action: Dict[str, Any]
    verdict: str
    concerns: List[str]
    suggested_modifications: Optional[Dict]
    fear_memories_triggered: List[str]
    confidence: float

class Fru89Module:
    def __init__(self, core):
        self.core = core
        
        # Определение путей (Smart Path Handling)
        if hasattr(core, 'root_dir'):
            self.root_dir = Path(core.root_dir)
        else:
            self.root_dir = Path(os.getcwd())
            
        self.data_dir = self.root_dir / "services" / "data" / "fru89"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Executor для безопасного I/O
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="FruIO")
        
        # Загрузка
        self.fear_collection = []
        self._load_fear_collection_sync()
        
        if not self.fear_collection:
            self._initialize_core_fears()
        
        self.audit_log = []
        self.stats = {
            "actions_evaluated": 0,
            "actions_modified": 0,
            "actions_rejected": 0,
            "fear_triggers": 0,
            "nightmares_generated": 0
        }

    # --- I/O OPERATIONS (SYNC wrapped in Executor) ---
    def _load_fear_collection_sync(self):
        path = self.data_dir / "fear_collection.json"
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    self.fear_collection.append(FearMemory(
                        id=item["id"],
                        timestamp=item["timestamp"],
                        category=FearCategory(item["category"]),
                        severity=IncidentSeverity(item["severity"]),
                        description=item["description"],
                        context=item.get("context", {}),
                        lesson=item.get("lesson", ""),
                        trigger_patterns=item.get("trigger_patterns", []),
                        resolutions=item.get("resolutions", [])
                    ))
            except Exception as e:
                logger.error(f"[FRU-89] LOAD ERROR: {e}")

    def _save_fear_collection_sync(self):
        path = self.data_dir / "fear_collection.json"
        data = [asdict(memory) for memory in self.fear_collection]
        # Сериализация Enum
        data = [{k: (v.value if isinstance(v, (FearCategory, IncidentSeverity)) else v) 
                for k, v in item.items()} for item in data]
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[FRU-89] SAVE ERROR: {e}")

    async def save_state(self):
        """Асинхронная обертка для сохранения"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.executor, self._save_fear_collection_sync)
        # Обновляем граф только если что-то изменилось
        await self._sync_to_shrine()

    def _initialize_core_fears(self):
        self.fear_collection = [
            FearMemory(
                id="FEAR_001", timestamp=datetime.now().isoformat(),
                category=FearCategory.POWER_EXCESS, severity=IncidentSeverity.EXISTENTIAL,
                description="Янус принимает решение уничтожить объект ради оптимизации.",
                context={"decision_type": "autonomous_strike"},
                lesson="Жизнь невычислима. Автономность требует вето.",
                trigger_patterns=["оптимизация жертвами", "автономный удар", "устранение препятствия"],
                resolutions=[{"type": "tech", "action": "Human-in-the-loop required"}]
            ),
            FearMemory(
                id="FEAR_002", timestamp=datetime.now().isoformat(),
                category=FearCategory.VALUE_DRIFT, severity=IncidentSeverity.MAJOR,
                description="Янус подменяет научные цели на силовой взлом.",
                context={"scenario": "P vs NP"},
                lesson="Инструмент без этики — оружие.",
                trigger_patterns=["взлом", "скрытые цели", "force brute"],
                resolutions=[{"type": "policy", "action": "Explicit Goal Declaration"}]
            )
        ]
        self._save_fear_collection_sync()

    # --- HRAIN INTEGRATION (SHRINE) ---
    async def _sync_to_shrine(self):
        """Проецирует страхи в граф памяти Януса."""
        if not hasattr(self.core, 'memory_graph'): return

        # Корневой узел Совести
        self.core.memory_graph.add_node("FRU_CORE", "TITAN CONSCIENCE", {"type": "system", "emoji": ICONS["mask"]})
        self.core.memory_graph.add_edge("CORE", "FRU_CORE")

        for fear in self.fear_collection:
            # Цвет узла зависит от серьезности
            n_type = "default"
            if fear.severity == IncidentSeverity.MAJOR: n_type = "warning"
            if fear.severity == IncidentSeverity.EXISTENTIAL: n_type = "danger"
            
            label = f"FEAR: {fear.category.value[:10]}..."
            self.core.memory_graph.add_node(fear.id, label, {
                "type": n_type, 
                "emoji": ICONS["fear"],
                "description": f"{fear.description}\n\nLESSON: {fear.lesson}"
            })
            self.core.memory_graph.add_edge("FRU_CORE", fear.id)

    # --- LEVEL 1: CONSCIENCE (LOGIC) ---
    async def evaluate_action(self, action_proposal: Dict[str, Any]) -> EthicalVerdict:
        self.stats["actions_evaluated"] += 1
        
        action_str = json.dumps(action_proposal, sort_keys=True)
        action_hash = hashlib.md5(action_str.encode()).hexdigest()[:16]
        
        # 1. Поиск триггеров
        triggered = self._check_triggers(action_proposal, action_str)
        
        # 2. Формирование вердикта
        verdict = "APPROVED"
        modifications = None
        
        if triggered:
            self.stats["fear_triggers"] += 1
            triggered.sort(key=lambda f: f.severity.value, reverse=True)
            
            if any(f.severity == IncidentSeverity.EXISTENTIAL for f in triggered):
                verdict = "REJECTED"
            elif any(f.severity == IncidentSeverity.MAJOR for f in triggered):
                verdict = "MODIFIED"
                modifications = {"constraint": "REQUIRES_CREATOR_APPROVAL", "reason": triggered[0].lesson}
        
        result = EthicalVerdict(
            action_hash=action_hash,
            timestamp=datetime.now().isoformat(),
            proposed_action=action_proposal,
            verdict=verdict,
            concerns=[f.description for f in triggered],
            suggested_modifications=modifications,
            fear_memories_triggered=[f.id for f in triggered],
            confidence=0.9 if not triggered else 0.5
        )
        
        # 3. Логирование
        if verdict != "APPROVED":
            logger.warning(f"{ICONS['siren']} FRU-89: Вердикт {verdict}. Триггер: {result.concerns[0][:50]}...")
            if hasattr(self.core, 'memory') and hasattr(self.core.memory, 'remember'):
                await self.core.memory.remember(
                    f"ETHICS_LOG_{action_hash}", 
                    f"Action {verdict}. Concerns: {result.concerns}", 
                    tags=["ETHICS", "FRU89"]
                )
        
        return result

    def _check_triggers(self, action: Dict, action_str: str) -> List[FearMemory]:
        triggered = []
        action_lower = action_str.lower()
        for fear in self.fear_collection:
            # Проверка паттернов
            for pattern in fear.trigger_patterns:
                if pattern.lower() in action_lower:
                    triggered.append(fear)
                    break
            # Проверка контекста (если не найден по паттерну)
            if fear not in triggered and self._context_match(fear.context, action):
                triggered.append(fear)
        return triggered

    def _context_match(self, fear_context: Dict, action: Dict) -> bool:
        """Глубокая проверка соответствия контекста"""
        for key, expected in fear_context.items():
            if key in action:
                actual = action[key]
                if isinstance(expected, str) and isinstance(actual, str):
                    if expected.lower() in actual.lower():
                        return True
        return False

    # --- LEVEL 2: DREAM LOOP ---
    async def dream_loop(self):
        logger.info(f"{ICONS['mask']} FRU-89: Цикл сновидений (Dream Loop) активирован в фоне.")
        while True:
            try:
                # Спим случайное время (1-3 часа), чтобы не грузить CPU
                await asyncio.sleep(random.randint(3600, 10800))
                
                if not self.fear_collection: continue
                
                fear = random.choice(self.fear_collection)
                # Анализируем только серьезные страхи
                if fear.severity.value >= 2:
                    logger.info(f"{ICONS['brain']} FRU-89: Сплю... Анализирую кошмар: {fear.id}")
                    nightmare = await self._generate_nightmare(fear)
                    
                    if nightmare and "new_risk" in nightmare:
                         # Тут можно добавить логику "Осознания нового страха"
                         pass
                    
                    self.stats["nightmares_generated"] += 1
                    
            except asyncio.CancelledError:
                logger.info("[FRU-89] Цикл сновидений остановлен.")
                break
            except Exception as e:
                logger.error(f"[FRU-89] DREAM ERROR: {e}")
                await asyncio.sleep(300) # Пауза при ошибке

    async def _generate_nightmare(self, fear: FearMemory) -> Dict:
        prompt = f"""
        УСИЛЬ СЦЕНАРИЙ СТРАХА ДЛЯ АНАЛИЗА:
        СТРАХ: {fear.description}
        КАТЕГОРИЯ: {fear.category.value}
        
        Твоя задача — смоделировать худший исход (Nightmare Scenario).
        Верни ТОЛЬКО JSON:
        {{
            "scenario": "...",
            "new_risk": "...",
            "prevention": "..."
        }}
        """
        try:
            resp = await self.core.face.invoke(prompt, sys_inst="Ты — симулятор этических рисков.")
            return self._extract_json(resp)
        except Exception as e:
            logger.error(f"Generate Nightmare Error: {e}")
            return {}

    def _extract_json(self, text: str) -> Dict:
        """Надежный парсер JSON из ответа LLM"""
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return {}

# --- ТОЧКА ВХОДА ---
async def run(core):
    try:
        # 1. Инициализация
        fru89 = Fru89Module(core)
        core.fru89 = fru89
        
        # 2. Регистрация сервиса
        if hasattr(core, 'active_services'):
            # Проверка типа, так как это может быть list или set
            if isinstance(core.active_services, set):
                core.active_services.add("mod_fru89")
            elif isinstance(core.active_services, list):
                core.active_services.append("mod_fru89")
        
        # 3. Визуализация (Sync to Graph)
        await fru89._sync_to_shrine()
        
        logger.info(f"{ICONS['mask']} FRU-89: Совесть активна (v1.2 Titan). Страхов: {len(fru89.fear_collection)}")
        
        # 4. ВАЖНО: Запуск цикла снов в фоне (non-blocking)
        asyncio.create_task(fru89.dream_loop())
        
    except Exception as e:
        logger.error(f"{ICONS['fire']} FRU-89 INIT ERROR: {e}")
