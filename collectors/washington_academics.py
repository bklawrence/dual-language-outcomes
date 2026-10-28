
name: Collect Washington dual-language inventory and academics

on:
  workflow_dispatch:
  schedule:
    - cron: '15 12 1 * *'

permissions:
  contents: read

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 55

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Download and audit Washington DL records
        run: python3 collectors/washington.py

      - name: Normalize dual-language programs in all languages
        run: python3 collectors/normalize_washington.py

      - name: Download and join Washington academic assessment results
        run: python3 collectors/washington_academics.py

      - name: Preserve data and audit outputs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: washington-research-${{ github.run_number }}
          path: output/washington/
          if-no-files-found: warn
          retention-days: 90
