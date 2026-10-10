def pytest_configure(config):
    config.addinivalue_line("markers", "spike_args(*args): extra command-line options for app.py")
