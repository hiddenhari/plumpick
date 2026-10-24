def main() -> int:
    # Imported lazily so `import plumpick` (e.g. in tests) doesn't load Qt.
    from plumpick.app.app import main as run

    return run()
