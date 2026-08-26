#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente somente-leitura para a API da LOC1 (SAP B1 Service Layer).

Por design, este módulo só implementa chamadas de LEITURA (Login + List).
Não existem métodos de Insert/Update aqui de propósito: mesmo que a
credencial usada tenha permissão de escrita no SAP B1, o código deste
cliente nunca faz uma chamada que altera dados.

Credenciais NUNCA ficam neste arquivo. Configure por variável de ambiente:

    export LOC1_BASE_URL="https://elevabr.loc1.com.br/api"
    export LOC1_USER="usuario@elevabr.com.br"
    export LOC1_PASSWORD="********"
    export LOC1_CONNECTION_ID="3"   # 3 = SBO_ELEVA_TST (teste) | 4 = ELEVABR PRD PRODUCAO
    export LOC1_LANGUAGE="pt-br"

Uso:
    from loc1_client import Loc1Client

    client = Loc1Client.from_env()
    client.login()
    registros = client.list_all("BillingHistory")
"""
import os
import time
from typing import Any, Dict, List, Optional

import requests

PAGE_SIZE = 100  # máximo aceito pela API por página


class Loc1ApiError(RuntimeError):
    """Erro retornado pela API da LOC1 (result=false)."""


class Loc1Client:
    def __init__(self, base_url: str, user: str, password: str,
                 connection_id: str, language: str = "pt-br",
                 timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.connection_id = connection_id
        self.language = language
        self.timeout = timeout
        self.session_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Loc1Client":
        missing = [k for k in ("LOC1_BASE_URL", "LOC1_USER", "LOC1_PASSWORD", "LOC1_CONNECTION_ID")
                   if not os.environ.get(k)]
        if missing:
            raise RuntimeError(
                "Faltam variáveis de ambiente: " + ", ".join(missing) +
                ". Veja o cabeçalho de loc1_client.py para o formato esperado."
            )
        return cls(
            base_url=os.environ["LOC1_BASE_URL"],
            user=os.environ["LOC1_USER"],
            password=os.environ["LOC1_PASSWORD"],
            connection_id=os.environ["LOC1_CONNECTION_ID"],
            language=os.environ.get("LOC1_LANGUAGE", "pt-br"),
        )

    def _post(self, path: str, payload: Dict[str, Any], max_retries: int = 4) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.strip('/')}/"
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
                    continue
                raise
        else:
            raise last_exc
        if str(data.get("result")).lower() == "false":
            raise Loc1ApiError(f"{path}: {data.get('error', 'erro desconhecido')}")
        return data

    def login(self) -> str:
        data = self._post("Login", {
            "User": self.user,
            "Password": self.password,
            "ConnectionID": self.connection_id,
            "Language": self.language,
        })
        session_id = data.get("SessionID") or data.get("sessionid") or data.get("session_id")
        if not session_id:
            raise Loc1ApiError(f"Login não retornou SessionID. Resposta bruta: {data}")
        self.session_id = session_id
        return session_id

    def list_page(self, entity: str, results_from: int = 1, results_to: int = PAGE_SIZE,
                  filters: Optional[List[Dict[str, str]]] = None,
                  order: Optional[List[Dict[str, str]]] = None,
                  extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.session_id:
            self.login()
        payload: Dict[str, Any] = {
            "SessionID": self.session_id,
            "ResultsFrom": results_from,
            "ResultsTo": results_to,
        }
        if filters:
            payload["Filters"] = filters
        if order:
            payload["Order"] = order
        if extra:
            payload.update(extra)
        return self._post(f"{entity}/List", payload)

    def list_all(self, entity: str, filters: Optional[List[Dict[str, str]]] = None,
                 order: Optional[List[Dict[str, str]]] = None,
                 extra: Optional[Dict[str, Any]] = None,
                 max_pages: int = 1000, sleep_between: float = 0.0,
                 page_size: int = PAGE_SIZE) -> List[Dict[str, Any]]:
        """Pagina automaticamente até não haver mais registros e retorna a lista completa."""
        all_records: List[Dict[str, Any]] = []
        start = 1
        for _ in range(max_pages):
            data = self.list_page(entity, results_from=start, results_to=start + page_size - 1,
                                   filters=filters, order=order, extra=extra)
            records = self._extract_records(data)
            if not records:
                break
            all_records.extend(records)
            if len(records) < page_size:
                break
            start += page_size
            if sleep_between:
                time.sleep(sleep_between)
        return all_records

    @staticmethod
    def _extract_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        for key in ("Data", "data", "Result", "result", "List", "list", "Records", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        for value in data.values():
            if isinstance(value, list):
                return value
        return []


if __name__ == "__main__":
    import json
    import sys

    entity = sys.argv[1] if len(sys.argv) > 1 else "BillingHistory"
    client = Loc1Client.from_env()
    client.login()
    print(f"Login OK. SessionID={client.session_id}")
    page = client.list_page(entity, results_from=1, results_to=5)
    print(json.dumps(page, indent=2, ensure_ascii=False)[:4000])
