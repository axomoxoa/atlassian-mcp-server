from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import dotenv_values


class ConfigurationError(ValueError):
    """Raised when required environment variables are missing."""


@dataclass(frozen=True)
class ServiceConfig:
    base_url: str
    deployment: Literal["cloud", "server"]
    auth_mode: Literal["bearer", "basic"]
    api_base_path: str
    bearer_token: str | None = None
    username: str | None = None
    password: str | None = None

    def public_summary(self) -> dict[str, str]:
        return {
            "base_url": self.base_url,
            "deployment": self.deployment,
            "auth_mode": self.auth_mode,
            "api_base_path": self.api_base_path,
            "credential": "configured",
            "username": self.username or "not set",
        }


@dataclass(frozen=True)
class AtlassianConfig:
    jira: ServiceConfig
    confluence: ServiceConfig

    SUPPORTED_TOOLSETS = frozenset({"core", "jira-read", "jira-write", "confluence-read", "confluence-write"})
    DEFAULT_TOOLSETS = frozenset({"core", "jira-read", "confluence-read"})

    @staticmethod
    def env_file_path() -> str:
        return os.getenv("ATLASSIAN_ENV_FILE", r"C:\Users\rober15\.mcp-secrets\atlassian.env")

    @classmethod
    def _load_values(cls) -> dict[str, str]:
        file_values = {
            key: value
            for key, value in dotenv_values(cls.env_file_path()).items()
            if isinstance(value, str)
        }
        env_values = {key: value for key, value in os.environ.items() if isinstance(value, str)}
        return {**file_values, **env_values}

    @classmethod
    def parse_toolsets(cls, raw_value: str | None) -> frozenset[str]:
        normalized = (raw_value or "all").strip().lower()
        if not normalized or normalized == "all":
            return cls.SUPPORTED_TOOLSETS
        if normalized == "default":
            return cls.DEFAULT_TOOLSETS

        requested = {part.strip().lower() for part in normalized.split(",") if part.strip()}
        expanded: set[str] = set()
        invalid: list[str] = []

        for toolset in requested:
            if toolset == "all":
                expanded.update(cls.SUPPORTED_TOOLSETS)
                continue
            if toolset == "default":
                expanded.update(cls.DEFAULT_TOOLSETS)
                continue
            if toolset not in cls.SUPPORTED_TOOLSETS:
                invalid.append(toolset)
                continue
            expanded.add(toolset)

        if invalid:
            supported = ", ".join(sorted(cls.SUPPORTED_TOOLSETS))
            invalid_values = ", ".join(sorted(invalid))
            raise ConfigurationError(
                f"Unsupported ATLASSIAN_MCP_TOOLSETS values: {invalid_values}. Supported values: all, default, {supported}"
            )

        if not expanded:
            raise ConfigurationError("ATLASSIAN_MCP_TOOLSETS did not resolve to any enabled toolsets")

        return frozenset(expanded)

    @classmethod
    def visible_toolsets_from_env(cls) -> frozenset[str]:
        values = cls._load_values()
        return cls.parse_toolsets(values.get("ATLASSIAN_MCP_TOOLSETS"))

    @staticmethod
    def _default_deployment(prefix: str, base_url: str) -> Literal["cloud", "server"]:
        lowered_url = base_url.lower()
        if prefix == "JIRA" and ".atlassian.net" in lowered_url:
            return "cloud"
        if prefix == "CONFLUENCE" and ".atlassian.net" in lowered_url:
            return "cloud"
        return "server"

    @staticmethod
    def _default_api_base_path(prefix: str, deployment: Literal["cloud", "server"]) -> str:
        if prefix == "JIRA":
            return "/rest/api/3" if deployment == "cloud" else "/rest/api/2"
        return "/wiki/rest/api" if deployment == "cloud" else "/rest/api"

    @classmethod
    def _service_config(cls, values: dict[str, str], prefix: str) -> ServiceConfig:
        base_url = values.get(f"{prefix}_URL", "").strip()
        deployment = values.get(f"{prefix}_DEPLOYMENT", "").strip().lower()
        auth_mode = (
            values.get(f"{prefix}_AUTH_MODE", "").strip().lower()
            or values.get("ATLASSIAN_AUTH_MODE", "").strip().lower()
            or values.get("AUTH_MODE", "").strip().lower()
        )
        api_base_path = values.get(f"{prefix}_API_BASE_PATH", "").strip()
        bearer_token = values.get(f"{prefix}_BEARER_TOKEN", "").strip()
        username = values.get(f"{prefix}_USERNAME", "").strip()
        password = values.get(f"{prefix}_PASSWORD", "").strip()

        if not base_url:
            raise ConfigurationError(f"Missing required environment variables: {prefix}_URL")

        resolved_deployment = deployment or cls._default_deployment(prefix, base_url)
        if resolved_deployment not in {"cloud", "server"}:
            raise ConfigurationError(
                f"Unsupported deployment for {prefix}: {resolved_deployment}. Use cloud or server"
            )

        resolved_api_base_path = api_base_path or cls._default_api_base_path(prefix, resolved_deployment)
        normalized_api_base_path = "/" + resolved_api_base_path.strip("/")

        resolved_auth_mode = auth_mode
        if not resolved_auth_mode:
            if username and password:
                resolved_auth_mode = "basic"
            elif bearer_token:
                resolved_auth_mode = "bearer"

        if resolved_auth_mode not in {"bearer", "basic"}:
            raise ConfigurationError(
                f"Unable to determine auth mode for {prefix}. Set {prefix}_AUTH_MODE to bearer or basic"
            )

        if resolved_auth_mode == "bearer":
            if not bearer_token:
                raise ConfigurationError(f"Missing required environment variables: {prefix}_BEARER_TOKEN")
            return ServiceConfig(
                base_url=base_url.rstrip("/"),
                deployment=resolved_deployment,
                auth_mode="bearer",
                api_base_path=normalized_api_base_path,
                bearer_token=bearer_token,
            )

        missing = [
            name
            for name, value in (
                (f"{prefix}_USERNAME", username),
                (f"{prefix}_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ConfigurationError(f"Missing required environment variables: {joined}")

        return ServiceConfig(
            base_url=base_url.rstrip("/"),
            deployment=resolved_deployment,
            auth_mode="basic",
            api_base_path=normalized_api_base_path,
            username=username,
            password=password,
        )

    @classmethod
    def from_env(cls) -> "AtlassianConfig":
        values = cls._load_values()
        return cls(
            jira=cls._service_config(values, "JIRA"),
            confluence=cls._service_config(values, "CONFLUENCE"),
        )

    def public_summary(self) -> dict[str, str]:
        return {
            "env_file": self.env_file_path(),
            "jira_base_url": self.jira.base_url,
            "jira_deployment": self.jira.deployment,
            "jira_auth_mode": self.jira.auth_mode,
            "jira_api_base_path": self.jira.api_base_path,
            "confluence_base_url": self.confluence.base_url,
            "confluence_deployment": self.confluence.deployment,
            "confluence_auth_mode": self.confluence.auth_mode,
            "confluence_api_base_path": self.confluence.api_base_path,
            "enabled_toolsets": ",".join(sorted(self.visible_toolsets_from_env())),
        }
