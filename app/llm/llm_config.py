import os
from dotenv import load_dotenv

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_LOCAL_MODEL = "qwen2.5:3b"
DEFAULT_LOCAL_MODEL_TITLE = "qwen2.5:0.5b"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

DEFAULT_TEMPERATURE = 0.2
TITLE_TEMPERATURE = 0.3

USE_OPENAI = False


# ============================================================
# API KEY CHECKS
# ============================================================

def gemini_available():
    key = os.getenv("Gemini_API_Key")
    return bool(key and key.strip())


def openai_available():
    key = os.getenv("OPENAI_API_KEY")
    return bool(key and key.strip())


# ============================================================
# MODEL FACTORIES
# ============================================================

def create_gemini():
    return ChatGoogleGenerativeAI(
        model=DEFAULT_GEMINI_MODEL,
        temperature=DEFAULT_TEMPERATURE,
    )


def create_openai():
    return ChatOpenAI(
        model=DEFAULT_OPENAI_MODEL,
        temperature=DEFAULT_TEMPERATURE,
    )


def create_ollama():
    return ChatOllama(
        model=DEFAULT_LOCAL_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        keep_alive=-1,
    )


def create_gemini_title():
    return ChatGoogleGenerativeAI(
        model=DEFAULT_GEMINI_MODEL,
        temperature=TITLE_TEMPERATURE,
    )


def create_openai_title():
    return ChatOpenAI(
        model=DEFAULT_OPENAI_MODEL,
        temperature=TITLE_TEMPERATURE,
    )


def create_ollama_title():
    return ChatOllama(
        model=DEFAULT_LOCAL_MODEL_TITLE,
        temperature=TITLE_TEMPERATURE,
        keep_alive=-1,
    )


# ============================================================
# RUNTIME FALLBACK MODEL
# ============================================================

class FallbackLLM:

    def __init__(self, providers):
        self.providers = providers

        self.current_provider = None
        self.current_llm = None

        # Tools are stored here after bind_tools()
        self.bound_tools = None
        self.bound_tool_kwargs = {}

    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    def _create_model(self, name, factory):

        try:

            model = factory()

            logger.info(
                f"Initialized LLM provider: {name}"
            )

            return model

        except Exception as e:

            logger.warning(
                f"Failed to initialize {name}: "
                f"{type(e).__name__}: {e}"
            )

            return None

    # --------------------------------------------------------
    # Bind tools
    # --------------------------------------------------------

    def bind_tools(self, tools, **kwargs):

        logger.info(
            f"Binding {len(tools)} tools to runtime fallback LLM"
        )

        # Create another fallback object so that the original
        # LLM remains usable for calls without tools.
        bound_llm = FallbackLLM(self.providers)

        bound_llm.bound_tools = tools
        bound_llm.bound_tool_kwargs = kwargs

        return bound_llm

    # --------------------------------------------------------
    # Apply tools to provider
    # --------------------------------------------------------

    def _bind_tools_if_needed(self, model):

        if self.bound_tools is None:
            return model

        try:

            return model.bind_tools(
                self.bound_tools,
                **self.bound_tool_kwargs
            )

        except Exception as e:

            logger.warning(
                f"Tool binding failed for provider: "
                f"{type(e).__name__}: {e}"
            )

            raise

    # --------------------------------------------------------
    # INVOKE
    # --------------------------------------------------------

    def invoke(self, *args, **kwargs):

        last_error = None

        for name, factory in self.providers:

            logger.info(
                f"Trying LLM provider: {name}"
            )

            try:

                # Create provider
                model = self._create_model(
                    name,
                    factory
                )

                if model is None:
                    continue

                # Bind tools if required
                if self.bound_tools is not None:

                    logger.info(
                        f"Binding tools to {name}"
                    )

                    model = self._bind_tools_if_needed(
                        model
                    )

                # Actual API call
                response = model.invoke(
                    *args,
                    **kwargs
                )

                # Success
                self.current_provider = name
                self.current_llm = model

                logger.info(
                    f"LLM request succeeded using {name}"
                )

                return response

            except Exception as e:

                last_error = e

                logger.error(
                    f"{name} failed during LLM invocation: "
                    f"{type(e).__name__}: {e}"
                )

                logger.warning(
                    f"Falling back from {name}..."
                )

                continue

        # ----------------------------------------------------
        # EVERYTHING FAILED
        # ----------------------------------------------------

        logger.critical(
            "ALL LLM PROVIDERS FAILED"
        )

        if last_error:
            raise last_error

        raise RuntimeError(
            "No LLM provider available."
        )

    # --------------------------------------------------------
    # ASYNC INVOKE
    # --------------------------------------------------------

    async def ainvoke(self, *args, **kwargs):

        last_error = None

        for name, factory in self.providers:

            logger.info(
                f"Trying async LLM provider: {name}"
            )

            try:

                model = self._create_model(
                    name,
                    factory
                )

                if model is None:
                    continue

                if self.bound_tools is not None:

                    model = self._bind_tools_if_needed(
                        model
                    )

                response = await model.ainvoke(
                    *args,
                    **kwargs
                )

                self.current_provider = name
                self.current_llm = model

                logger.info(
                    f"Async LLM request succeeded using {name}"
                )

                return response

            except Exception as e:

                last_error = e

                logger.error(
                    f"{name} async invocation failed: "
                    f"{type(e).__name__}: {e}"
                )

                logger.warning(
                    f"Falling back from {name}..."
                )

                continue

        logger.critical(
            "ALL ASYNC LLM PROVIDERS FAILED"
        )

        if last_error:
            raise last_error

        raise RuntimeError(
            "No LLM provider available."
        )


# ============================================================
# MAIN CHAT LLM
# ============================================================

def load_llm():

    providers = []

    # Gemini first
    if gemini_available():

        providers.append(
            (
                "Gemini",
                create_gemini
            )
        )

    # OpenAI optional
    if USE_OPENAI and openai_available():

        providers.append(
            (
                "OpenAI",
                create_openai
            )
        )

    # Ollama ALWAYS LAST
    providers.append(
        (
            "Ollama",
            create_ollama
        )
    )

    logger.info(
        "Runtime LLM fallback chain configured: "
        + " -> ".join(
            name for name, _ in providers
        )
    )

    return FallbackLLM(providers)


# ============================================================
# TITLE LLM
# ============================================================

def generate_title_llm():

    providers = []

    # Gemini
    if gemini_available():

        providers.append(
            (
                "Gemini",
                create_gemini_title
            )
        )

    # OpenAI optional
    if USE_OPENAI and openai_available():

        providers.append(
            (
                "OpenAI",
                create_openai_title
            )
        )

    # Ollama
    providers.append(
        (
            "Ollama",
            create_ollama_title
        )
    )

    logger.info(
        "Runtime title fallback chain configured: "
        + " -> ".join(
            name for name, _ in providers
        )
    )

    return FallbackLLM(providers)


# ============================================================
# GLOBAL INSTANCES
# ============================================================

llm = load_llm()

gen_title = generate_title_llm()