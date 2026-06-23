"""Browser session — navigation, SSRF redirect guard, network hooks."""

from __future__ import annotations

from typing import Any, Callable

from agentarmor.webscan.url_validator import validate_page_url


class BrowserSession:
    def __init__(
        self,
        page: Any,
        *,
        allowlist: list[str] | None = None,
        blocklist: list[str] | None = None,
    ) -> None:
        self.page = page
        self._allowlist = allowlist or []
        self._blocklist = blocklist or []
        self._network_log: list[dict[str, Any]] = []
        self._setup_guards()

    def _setup_guards(self) -> None:
        async def _route_handler(route: Any) -> None:
            req_url = route.request.url
            result = validate_page_url(
                req_url,
                allowlist=self._allowlist,
                blocklist=self._blocklist,
                resolve_dns=False,
            )
            if not result.ok:
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        self.page.route("**/*", _route_handler)

        def _on_response(response: Any) -> None:
            self._network_log.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                }
            )

        self.page.on("response", _on_response)

    async def goto(self, url: str, timeout_ms: int = 30000) -> None:
        result = validate_page_url(
            url,
            allowlist=self._allowlist,
            blocklist=self._blocklist,
        )
        if not result.ok:
            raise ValueError(result.error)
        await self.page.goto(result.normalized_url, wait_until="domcontentloaded", timeout=timeout_ms)
        await self.page.wait_for_timeout(500)

    @property
    def network_log(self) -> list[dict[str, Any]]:
        return list(self._network_log)
