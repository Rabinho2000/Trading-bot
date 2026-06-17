import importlib
import sys
import types


def test_dashboard_app_imports_without_error(monkeypatch):
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.session_state = {}
    fake_streamlit.sidebar = fake_streamlit
    fake_streamlit.set_page_config = lambda **_kwargs: None
    fake_streamlit.markdown = lambda *_args, **_kwargs: None
    fake_streamlit.multiselect = lambda *_args, **kwargs: kwargs.get("default", [])
    fake_streamlit.selectbox = lambda *_args, **_kwargs: _args[1][0]
    fake_streamlit.date_input = lambda *_args, **kwargs: kwargs.get("value")
    fake_streamlit.number_input = lambda *_args, **kwargs: kwargs.get("value", 0)
    fake_streamlit.checkbox = lambda *_args, **kwargs: kwargs.get("value", False)
    fake_streamlit.button = lambda *_args, **_kwargs: False
    fake_streamlit.spinner = lambda *_args, **_kwargs: types.SimpleNamespace(__enter__=lambda self: None, __exit__=lambda self, *exc: False)
    fake_streamlit.success = lambda *_args, **_kwargs: None
    fake_streamlit.error = lambda *_args, **_kwargs: None
    fake_streamlit.warning = lambda *_args, **_kwargs: None
    fake_streamlit.info = lambda *_args, **_kwargs: None
    fake_streamlit.rerun = lambda: None
    fake_streamlit.columns = lambda count: [fake_streamlit for _ in range(count)]
    fake_streamlit.metric = lambda *_args, **_kwargs: None
    fake_streamlit.dataframe = lambda *_args, **_kwargs: None
    fake_streamlit.bar_chart = lambda *_args, **_kwargs: None
    fake_streamlit.line_chart = lambda *_args, **_kwargs: None
    fake_streamlit.scatter_chart = lambda *_args, **_kwargs: None
    fake_streamlit.download_button = lambda *_args, **_kwargs: None

    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    module = importlib.import_module("dashboard.app")

    assert module is not None
