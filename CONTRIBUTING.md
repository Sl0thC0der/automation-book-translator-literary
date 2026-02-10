# Contributing

Contributions are welcome. Please follow these guidelines.

## Development Setup

```bash
git clone <repository-url>
cd automation-book-translator-literary
./scripts/setup.sh
```

## Testing

```bash
# Integration tests
./scripts/test-translation.sh

# Upstream tests
python -m pytest tests/
```

## Creating a Profile

1. Copy `examples/profiles/_template.json`
2. Edit style instructions, protected nouns, glossary seeds
3. Test with `--test --test_num 5`
4. Submit as PR with description of the target genre/use case

## Commit Messages

Follow conventional commits:
```
feat: add romance profile with emotional register handling
fix: glossary extraction handles markdown fences
docs: add French translation tips to profiles.md
```

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/romance-profile`)
3. Commit your changes
4. Push and open a PR
5. Describe what changed and why
