"""
LLM service factory for creating configured LLM clients.
"""

from typing import Any, Optional, Union
import asyncio
import logging
from contextlib import asynccontextmanager

from pydantic_ai.models import Model, ModelSettings
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.exceptions import UnexpectedModelBehavior
import openai
from anthropic import AsyncAnthropic
from pydantic import ValidationError
from pydantic_ai.models.openai import OpenAIModelSettings
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ModelRequest,
    TextPart,
)
from openai import OpenAI

# Import Copilot SDK
# Note: In a real environment, we'd handle potential import errors if the SDK isn't installed,
# but here we assume it is as per requirements.
from copilot import CopilotClient

from gatomia.src.config import Config

logger = logging.getLogger(__name__)


class CopilotModel(Model):
    """
    Adapter for GitHub Copilot SDK to be compatible with pydantic-ai Model.
    """

    def __init__(self, model_name: str, config: Config):
        self._model_name = model_name
        self.config = config
        self._client: Optional[CopilotClient] = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "github"

    async def agent_model(
        self,
        function_tools: list[Any],
        allow_text_result: bool,
        result_tools: list[Any],
    ) -> Any:
        # For simplicity in this adapter, we might not fully implementing function tools
        # unless copilot-sdk supports them in a way pydantic-ai expects.
        # This is a basic implementation for text completion.
        # If precise pydantic-ai integration is needed, more work is required here.
        raise NotImplementedError("CopilotModel does not support agent_model directly yet.")

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: Optional[ModelSettings] = None,
        model_request: Optional[ModelRequest] = None,
    ) -> ModelResponse:
        """
        Make a request to the model.
        """
        async with self._get_client() as client:
            session = await client.create_session({"model": self.model_name})

            # Convert messages to prompt string or proper format
            # Copilot SDK cookbook mainly shows single prompt or chat-like interaction.
            # We'll concatenate messages for now or use the last user message.
            # Ideally we should use the proper chat format if SDK supports it.

            prompt = ""
            for msg in messages:
                for part in msg.parts:
                    if isinstance(part, TextPart):
                        prompt += f"{part.content}\n"

            response = await session.send_and_wait({"prompt": prompt})

            # Extract content from response
            # Assuming response.data.content based on research
            content = response.data.content

            return ModelResponse(parts=[TextPart(content=content)])

    @asynccontextmanager
    async def _get_client(self):
        # We create a new client or manage a lifecycle.
        # For simple request/response, creating/stopping is safe but maybe inefficient.
        auth_info = {}
        if self.config.copilot_token:
            auth_info["token"] = self.config.copilot_token

        client = CopilotClient(auth_info) if auth_info else CopilotClient()
        try:
            await client.start()
            yield client
        finally:
            await client.stop()


class OpenRouterModel(OpenAIModel):
    """Custom model for OpenRouter to handle include_reasoning and validation errors."""

    def __init__(self, model_name: str, include_reasoning: bool = False, **kwargs):
        # Remove base_url and api_key from kwargs if present, as OpenAIModel doesn't accept them
        kwargs.pop("base_url", None)
        kwargs.pop("api_key", None)
        # We also don't pass them to super().__init__ because it doesn't accept them.
        # Configuration relies on environment variables (OPENAI_BASE_URL, OPENAI_API_KEY)
        super().__init__(model_name, **kwargs)
        self.include_reasoning = include_reasoning

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: Optional[ModelSettings] = None,
        model_request: Optional[ModelRequest] = None,
    ) -> ModelResponse:
        """Override request to include reasoning flag and handle validation errors."""
        # Inject include_reasoning into extra_body if not present
        if self.include_reasoning:
            if model_settings is None:
                model_settings = OpenAIModelSettings()
            if model_settings.extra_body is None:
                model_settings.extra_body = {}
            model_settings.extra_body["reasoning"] = {"enabled": True}

        try:
            return await super().request(messages, model_settings, model_request)
        except ValidationError as e:
            logger.error(f"OpenRouter Validation Error: {e.json()}")
            raise UnexpectedModelBehavior(
                f"Model response validation failed: {e.json()}", raw_detail=e.json()
            ) from e
        except openai.APIStatusError as e:
            logger.error(f"OpenRouter API Error: {e.response.text}")
            raise UnexpectedModelBehavior(
                f"OpenRouter API error: {e.response.text}", raw_detail=e.response.text
            ) from e
        except Exception as e:
            # Catch other potential errors and wrap them
            logger.error(f"OpenRouter unexpected error: {e}")
            raise UnexpectedModelBehavior(f"OpenRouter unexpected error: {e}") from e


def create_main_model(config: Config) -> Union[OpenRouterModel, CopilotModel, AnthropicModel]:
    """Create the main LLM model from configuration."""
    if config.llm_provider == "copilot":
        return CopilotModel(model_name=config.main_model, config=config)

    if config.llm_provider == "anthropic":
        if config.llm_api_key:
            import os

            os.environ["ANTHROPIC_API_KEY"] = config.llm_api_key

        # Only set custom base URL if it's not the default localhost (which is for local proxies/copilot)
        # and not empty.
        default_base_url = "http://0.0.0.0:4000/"
        if config.llm_base_url and config.llm_base_url != default_base_url:
            import os

            os.environ["ANTHROPIC_BASE_URL"] = config.llm_base_url

        # Pass explicit timeout to avoid "Streaming is required" error for >10min requests
        return AnthropicModel(config.main_model, settings={"timeout": 600.0})

    # Set environment variables for pydantic-ai OpenAIModel
    if config.llm_base_url:
        import os

        os.environ["OPENAI_BASE_URL"] = config.llm_base_url
    if config.llm_api_key:
        import os

        os.environ["OPENAI_API_KEY"] = config.llm_api_key

    return OpenRouterModel(
        model_name=config.main_model,
        include_reasoning=config.include_reasoning,
    )


def create_fallback_model(config: Config) -> Union[OpenRouterModel, CopilotModel, AnthropicModel]:
    """Create the fallback LLM model from configuration."""
    if config.llm_provider == "copilot":
        return CopilotModel(model_name=config.fallback_model, config=config)

    if config.llm_provider == "anthropic":
        if config.llm_api_key:
            import os

            os.environ["ANTHROPIC_API_KEY"] = config.llm_api_key

        # Only set custom base URL if it's not the default localhost
        # Only set custom base URL if it's not the default localhost
        default_base_url = "http://0.0.0.0:4000/"
        if config.llm_base_url and config.llm_base_url != default_base_url:
            import os

            os.environ["ANTHROPIC_BASE_URL"] = config.llm_base_url

        # Pass explicit timeout
        return AnthropicModel(config.fallback_model, settings={"timeout": 600.0})

    # Set environment variables just in case (though main model creation likely set them)
    if config.llm_base_url:
        import os

        os.environ["OPENAI_BASE_URL"] = config.llm_base_url
    if config.llm_api_key:
        import os

        os.environ["OPENAI_API_KEY"] = config.llm_api_key

    return OpenRouterModel(
        model_name=config.fallback_model,
        include_reasoning=config.include_reasoning,
    )


def create_fallback_models(config: Config) -> FallbackModel:
    """Create fallback models chain from configuration."""
    main = create_main_model(config)
    fallback = create_fallback_model(config)
    return FallbackModel(main, fallback)


def create_openai_client(config: Config) -> OpenAI:
    """Create OpenAI client from configuration."""
    return OpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)


async def call_llm(
    prompt: str,
    config: Config,
    model: str = None,
    temperature: float = 0.0,
    include_reasoning: Optional[bool] = None,
) -> str:
    """
    Call LLM with the given prompt.

    Args:
        prompt: The prompt to send
        config: Configuration containing LLM settings
        model: Model name (defaults to config.main_model)
        temperature: Temperature setting
        include_reasoning: Optional override for reasoning flag

    Returns:
        LLM response text
    """
    if model is None:
        model = config.main_model

    if include_reasoning is None:
        include_reasoning = config.include_reasoning

    if config.llm_provider == "copilot":
        # Copilot implementation
        auth_info = {}
        if config.copilot_token:
            auth_info["token"] = config.copilot_token

        client = CopilotClient(auth_info) if auth_info else CopilotClient()
        try:
            await client.start()
            session = await client.create_session({"model": model})
            response = await session.send_and_wait({"prompt": prompt})
            return response.data.content
        finally:
            await client.stop()
    elif config.llm_provider == "anthropic":
        # Anthropic implementation
        # Check for custom base URL (ignoring default localhost)
        default_base_url = "http://0.0.0.0:4000/"
        base_url = None
        if config.llm_base_url and config.llm_base_url != default_base_url:
            base_url = config.llm_base_url

        client = AsyncAnthropic(api_key=config.llm_api_key, base_url=base_url, timeout=600.0)
        response = await client.messages.create(
            model=model,
            max_tokens=config.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.content[0].text
    else:
        # OpenAI implementation (wrapped in asyncio)
        client = create_openai_client(config)

        # Run synchronous OpenAI call in a thread to keep this function async
        return await asyncio.to_thread(
            _call_openai_sync,
            client,
            model,
            prompt,
            temperature,
            config.max_tokens,
            include_reasoning,
        )


def _call_openai_sync(client, model, prompt, temperature, max_tokens, include_reasoning=False):
    extra_body = {}
    if include_reasoning:
        extra_body["reasoning"] = {"enabled": True}

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=extra_body,
    )
    return response.choices[0].message.content
