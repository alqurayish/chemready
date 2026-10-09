"""Extract one SDS: privacy check, build the prompt, call the model, return the result."""

from dataclasses import dataclass

from chemready.extraction.llm import LlmClient, LlmUsage, extract
from chemready.extraction.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_document_text
from chemready.pdf.parse import ParsedDocument
from chemready.schema import SdsExtraction


class PrivacyError(Exception):
    """Refused: private factory data must never go to a free AI tier."""


class ScannedDocumentError(Exception):
    """The PDF is a scan with no text. It needs OCR before extraction."""


@dataclass(frozen=True)
class ExtractionRun:
    extraction: SdsExtraction
    usage: LlmUsage
    prompt_version: str


def extract_sds(document: ParsedDocument, client: LlmClient, *, private: bool) -> ExtractionRun:
    """Extract the key fields from a parsed SDS.

    private=True means the file came from a factory (not a public download). Such
    files are only sent to a provider that is allowed to receive private data.
    """
    if private and not client.allows_private_data:
        raise PrivacyError(
            f"Refused: '{client.provider}' is a free tier. Private factory files must use a local "
            "model (Ollama) or a paid tier."
        )
    if document.is_scanned:
        raise ScannedDocumentError("This PDF is a scan without text. OCR is needed before extraction.")
    result = extract(SdsExtraction, SYSTEM_PROMPT, build_document_text(document), client)
    return ExtractionRun(extraction=result.output, usage=result.usage, prompt_version=PROMPT_VERSION)
