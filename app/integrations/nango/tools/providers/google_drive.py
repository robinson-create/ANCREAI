"""Google Drive tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "google_drive_search_files",
            "description": "Rechercher des fichiers dans Google Drive par nom ou contenu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche (nom de fichier ou contenu)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre max de résultats (défaut: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_drive_list_folder",
            "description": "Lister le contenu d'un dossier Google Drive. Sans folder_id, liste la racine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": "ID du dossier (défaut: 'root' pour la racine)",
                        "default": "root",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre max de résultats (défaut: 20)",
                        "default": 20,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_drive_get_file",
            "description": "Obtenir les métadonnées d'un fichier Google Drive par son ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID du fichier Google Drive",
                    },
                },
                "required": ["file_id"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Google Drive tool via Nango proxy."""
    if tool_name == "google_drive_search_files":
        query = args["query"]
        max_results = args.get("max_results", 10)
        resp = await proxy.get(
            "/drive/v3/files",
            params={
                "q": f"fullText contains '{query}' or name contains '{query}'",
                "pageSize": max_results,
                "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink,owners)",
                "orderBy": "modifiedTime desc",
            },
        )
        data = resp.json()
        files = [
            {
                "id": f["id"],
                "name": f.get("name", ""),
                "type": f.get("mimeType", ""),
                "modified": f.get("modifiedTime", ""),
                "size": f.get("size", ""),
                "url": f.get("webViewLink", ""),
            }
            for f in data.get("files", [])
        ]
        return json.dumps({"files": files, "count": len(files)}, ensure_ascii=False)

    elif tool_name == "google_drive_list_folder":
        folder_id = args.get("folder_id", "root")
        max_results = args.get("max_results", 20)
        resp = await proxy.get(
            "/drive/v3/files",
            params={
                "q": f"'{folder_id}' in parents and trashed = false",
                "pageSize": max_results,
                "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
                "orderBy": "folder,name",
            },
        )
        data = resp.json()
        items = [
            {
                "id": f["id"],
                "name": f.get("name", ""),
                "type": f.get("mimeType", ""),
                "is_folder": f.get("mimeType") == "application/vnd.google-apps.folder",
                "modified": f.get("modifiedTime", ""),
                "url": f.get("webViewLink", ""),
            }
            for f in data.get("files", [])
        ]
        return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)

    elif tool_name == "google_drive_get_file":
        file_id = args["file_id"]
        resp = await proxy.get(
            f"/drive/v3/files/{file_id}",
            params={
                "fields": "id,name,mimeType,modifiedTime,size,webViewLink,description,owners,shared",
            },
        )
        data = resp.json()
        file_info = {
            "id": data.get("id", ""),
            "name": data.get("name", ""),
            "type": data.get("mimeType", ""),
            "modified": data.get("modifiedTime", ""),
            "size": data.get("size", ""),
            "url": data.get("webViewLink", ""),
            "description": data.get("description", ""),
            "shared": data.get("shared", False),
        }
        return json.dumps({"file": file_info}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
