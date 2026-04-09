import ast
import logging
import re
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser

logger = logging.getLogger(__name__)


class CustomJsonOutputParser(BaseOutputParser[Any]):
    """
    Parses a JSON-like string from the LLM output.
    Handles markdown code blocks and uses ast.literal_eval for safe parsing.
    """

    def parse(self, text: str) -> Any:
        """
        Parses the LLM output text into a Python dictionary.
        """
        if "</answer>" in text:
            # 提取标签内的内容（兼容可能的空格/换行）
            match = re.search(r"<answer>(.*?)</answer>", text, re.S)
            if match:
                text = match.group(1).strip()
        print(text)
        # Remove markdown code blocks
        cleaned_text = re.sub(r"```(json)?", "", text).strip()

        # Remove comments
        cleaned_text = re.sub(r"//.*?\n|#.*?\n", "\n", cleaned_text)

        # Join lines and remove extra whitespace
        cleaned_text = "\n".join([line.strip() for line in cleaned_text.splitlines() if line.strip()])

        try:
            # Use ast.literal_eval for safe evaluation of Python literals
            return ast.literal_eval(cleaned_text)
        except (SyntaxError, ValueError) as e:
            logger.warning(f"[Parser Error] {e}\n[LLM原始输出]\n{text}")
            raise OutputParserException(f"Failed to parse LLM output: {e}") from e
