#! /usr/bin/env bash

rm -f dist/zix

python -m zipapp "src" \
    --output "dist/zix" \
    --python "/usr/bin/env python3"