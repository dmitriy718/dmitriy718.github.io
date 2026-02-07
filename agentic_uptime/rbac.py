from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set


@dataclass
class Role:
    name: str
    allow: Set[str]


class RBAC:
    def __init__(self, roles: Iterable[Role], agent_name: str, agent_role: str) -> None:
        self._roles: Dict[str, Role] = {role.name: role for role in roles}
        self.agent_name = agent_name
        self.agent_role = agent_role

    def authorize(self, action: str) -> bool:
        role = self._roles.get(self.agent_role)
        if not role:
            return False
        return action in role.allow or "*" in role.allow

    def require(self, action: str) -> None:
        if not self.authorize(action):
            raise PermissionError(f"RBAC denied action '{action}' for {self.agent_name}")
