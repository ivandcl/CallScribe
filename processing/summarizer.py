import logging
from pathlib import Path

import requests

from processing.prompts import SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_PROMPT

logger = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 100_000


class Summarizer:
    def __init__(self, provider: str = "anthropic", api_key: str = None,
                 model: str = None, ollama_url: str = None, ollama_model: str = None):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.ollama_url = ollama_url or "http://localhost:11434"
        self.ollama_model = ollama_model or "llama3"

    def summarize(self, transcript_path: str, output_dir: str,
                  recording_date: str) -> str:
        transcript_path = Path(transcript_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        transcript = transcript_path.read_text(encoding="utf-8")
        if not transcript.strip():
            raise ValueError("La transcripcion esta vacia")

        output_path = output_dir / f"{transcript_path.stem}.md"

        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            summary = self._summarize_long(transcript, recording_date)
        else:
            summary = self._call_llm(transcript, recording_date)

        output_path.write_text(summary, encoding="utf-8")
        logger.info("Acta generada: %s", output_path)
        return str(output_path)

    def _summarize_long(self, transcript: str, recording_date: str) -> str:
        # Split into chunks and summarize each, then consolidate
        chunks = []
        for i in range(0, len(transcript), MAX_TRANSCRIPT_CHARS):
            chunks.append(transcript[i : i + MAX_TRANSCRIPT_CHARS])

        partial_summaries = []
        for idx, chunk in enumerate(chunks):
            logger.info("Resumiendo parte %d/%d...", idx + 1, len(chunks))
            partial = self._call_llm(chunk, recording_date)
            partial_summaries.append(partial)

        if len(partial_summaries) == 1:
            return partial_summaries[0]

        # Consolidate
        combined = "\n\n---\n\n".join(partial_summaries)
        consolidation_prompt = (
            "A continuacion hay varios resumenes parciales de una misma reunion. "
            "Consolida toda la informacion en una sola acta final con el mismo formato. "
            "Elimina redundancias y combina las secciones.\n\n" + combined
        )
        return self._call_llm(consolidation_prompt, recording_date)

    def _call_llm(self, transcript: str, recording_date: str) -> str:
        user_prompt = SUMMARY_USER_PROMPT.format(
            fecha=recording_date,
            transcription=transcript,
        )

        if self.provider == "anthropic" and self.api_key:
            return self._call_anthropic(user_prompt)

        if self.provider == "ollama" or not self.api_key:
            try:
                return self._call_ollama(user_prompt)
            except Exception as e:
                if self.api_key:
                    logger.warning("Ollama fallo (%s), intentando con Anthropic...", e)
                    return self._call_anthropic(user_prompt)
                raise

        return self._call_anthropic(user_prompt)

    def _call_anthropic(self, user_prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model or "claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    def _call_ollama(self, user_prompt: str) -> str:
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.ollama_model,
                "system": SUMMARY_SYSTEM_PROMPT,
                "prompt": user_prompt,
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["response"]
