name: Market Pulse Data

on:
  workflow_dispatch:
  schedule:
    # Every 6 hours (UTC). Change if you want.
    - cron: "0 */6 * * *"

permissions:
  contents: write

concurrency:
  group: market-pulse-data
  cancel-in-progress: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Generate market.json
        run: python scripts/update_market_pulse.py

      - name: Commit & push if changed
        run: |
          git config user.name "ykcapitalholdings-bot"
          git config user.email "ykcapitalholdings@gmail.com"

          if git status --porcelain | grep -q "data/market.json"; then
            git add data/market.json
            git commit -m "Update market pulse data"
            git push
          else
            echo "No changes to commit."
          fi
