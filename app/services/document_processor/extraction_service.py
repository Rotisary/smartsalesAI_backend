import io
from typing import Optional


class ExtractionService:

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber")

        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError("python-docx is not installed. Run: pip install python-docx")

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    
    @staticmethod
    def _extract_text(file_bytes: bytes) -> str:

        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")

    @staticmethod       
    def extract_text(file_bytes: bytes, content_type: str, filename: str) -> str:
        """
        Return the full plain-text content of the file.
        Raises ValueError if the format is unsupported or extraction fails.
        """
        ct = content_type.lower()
        fn = filename.lower()

        if ct == "application/pdf" or fn.endswith(".pdf"):
            return ExtractionService._extract_pdf(file_bytes)

        if (
            ct in (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            )
            or fn.endswith(".docx")
            or fn.endswith(".doc")
        ):
            return ExtractionService._extract_docx(file_bytes)

        if ct.startswith("text/") or fn.endswith(".txt") or fn.endswith(".md"):
            return ExtractionService._extract_text(file_bytes)

        raise ValueError(
            f"Unsupported file type: {content_type}. "
            "Supported formats: PDF, DOCX, TXT, MD"
        )
