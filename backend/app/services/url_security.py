import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    pass


Resolver = Callable[[str, int], Awaitable[list[str]]]


async def system_resolver(hostname: str, port: int) -> list[str]:
    def resolve() -> list[str]:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return list({record[4][0] for record in records})

    return await asyncio.to_thread(resolve)


class UrlSecurityPolicy:
    def __init__(self, resolver: Resolver = system_resolver) -> None:
        self.resolver = resolver

    async def validate(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise UnsafeUrlError("Seules les URL HTTP et HTTPS sont autorisées.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise UnsafeUrlError("URL distante invalide.")

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise UnsafeUrlError("Les adresses locales sont interdites.")

        try:
            literal_ip = ipaddress.ip_address(hostname)
            addresses = [str(literal_ip)]
        except ValueError:
            try:
                addresses = await self.resolver(
                    hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                )
            except OSError as exc:
                raise UnsafeUrlError("Le nom d’hôte ne peut pas être résolu.") from exc

        if not addresses:
            raise UnsafeUrlError("Le nom d’hôte ne possède aucune adresse IP.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise UnsafeUrlError(f"Adresse réseau non publique interdite : {ip}.")

