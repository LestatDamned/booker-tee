import os
import resource
import sys
from pathlib import Path

from app.features.imports.parsers.sidecar.protocol import RESOURCE_LIMIT_EXIT_CODE


def main() -> None:
    input_path, extension, limits_json, memory, cpu, response_max = sys.argv[1:]
    resource.setrlimit(resource.RLIMIT_AS, (int(memory), int(memory)))
    resource.setrlimit(resource.RLIMIT_CPU, (int(cpu), int(cpu)))
    os.nice(10)

    try:
        from app.features.imports.parsers.extractors.limits import (
            StatementExtractionLimits,
            StatementResourceLimitError,
        )
        from app.features.imports.parsers.extractors.resolver import StatementExtractorResolver
    except (MemoryError, ImportError, OSError):
        raise SystemExit(RESOURCE_LIMIT_EXIT_CODE) from None

    try:
        limits = StatementExtractionLimits.model_validate_json(limits_json)
        extracted = StatementExtractorResolver(limits=limits).extract(Path(input_path))
        payload = extracted.model_dump_json().encode()
        if len(payload) > int(response_max):
            raise MemoryError
        sys.stdout.buffer.write(payload)
    except MemoryError:
        raise SystemExit(RESOURCE_LIMIT_EXIT_CODE) from None
    except StatementResourceLimitError:
        raise SystemExit(RESOURCE_LIMIT_EXIT_CODE) from None


if __name__ == "__main__":
    main()
