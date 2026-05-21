from rest_framework import serializers


class RestructureRequestSerializer(serializers.Serializer):
    input_text = serializers.CharField(trim_whitespace=True, required=False, allow_blank=True)
    input_file = serializers.FileField(required=False, allow_empty_file=False)
    source_context = serializers.CharField(required=False, allow_blank=True, default="")
    highlight_words = serializers.ListField(child=serializers.CharField(), required=False)
    target_language = serializers.CharField(required=False, default="en")
    mixed_output = serializers.CharField(required=False, default="taglish")
    metrics = serializers.DictField(required=False)

    def _extract_text_from_docx(self, file_bytes):
        """Extract text from .docx (Word) file."""
        try:
            from docx import Document
            from io import BytesIO
        except ImportError:
            raise serializers.ValidationError("python-docx is required to process Word files.")
        
        try:
            doc = Document(BytesIO(file_bytes))
            text_parts = [para.text for para in doc.paragraphs]
            return "\n".join(text_parts)
        except Exception as e:
            raise serializers.ValidationError(f"Failed to extract text from Word file: {str(e)}")

    def _extract_text_from_pdf(self, file_bytes):
        """Extract text from .pdf file."""
        try:
            from PyPDF2 import PdfReader
            from io import BytesIO
        except ImportError:
            raise serializers.ValidationError("PyPDF2 is required to process PDF files.")
        
        try:
            pdf_reader = PdfReader(BytesIO(file_bytes))
            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
            return "\n".join(text_parts)
        except Exception as e:
            raise serializers.ValidationError(f"Failed to extract text from PDF file: {str(e)}")

    def validate(self, attrs):
        input_text = (attrs.get("input_text") or "").strip()
        input_file = attrs.get("input_file")

        if not input_text and not input_file:
            raise serializers.ValidationError("Provide input_text or input_file.")

        if input_file:
            raw_bytes = input_file.read()
            filename = input_file.name.lower()
            
            if filename.endswith(".pdf"):
                input_text = self._extract_text_from_pdf(raw_bytes)
            elif filename.endswith(".docx"):
                input_text = self._extract_text_from_docx(raw_bytes)
            else:
                # Try as UTF-8 text
                try:
                    input_text = raw_bytes.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise serializers.ValidationError("input_file must be UTF-8 text, PDF, or Word (.docx).") from error

            input_text = input_text.strip()

        if not input_text:
            raise serializers.ValidationError("Input text cannot be empty.")

        attrs["input_text"] = input_text
        return attrs
