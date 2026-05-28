import hashlib
import json
from abc import ABC, abstractmethod


class BaseParser(ABC):
    """
    Contract every source parser must satisfy.

    parse() returns rows with two keys:
      - raw_data: the original row exactly as received (source-of-truth)
      - canonical: the mapped/cleaned row used by validation and normalization

    Keeping raw_data separate from canonical means we never lose the original
    even when our column mapping is wrong.
    """

    @abstractmethod
    def parse(self, file_obj):
        """
        Accept a file-like object.
        Return list of { "row_number": int, "raw_data": dict, "canonical": dict }
        """
        raise NotImplementedError

    @staticmethod
    def checksum(row_dict):
        serialized = json.dumps(row_dict, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()
