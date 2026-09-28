from __future__ import annotations

import json
import os

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_health_observability import operational_read_model


def main() -> int:
    config = ControlPlaneConfig.from_env()
    model = operational_read_model(config)
    print(json.dumps(model, sort_keys=True, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
