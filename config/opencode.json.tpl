{
  "plugins": [
    "superpowers@git+https://github.com/obra/superpowers.git",
    "videowizard@git+https://github.com/bitm4ncer/VideoWizard.git",
    "@plannotator/opencode@latest",
    "opencode-mem@latest",
    "@tarquinen/opencode-dcp@latest",
    "opencode-scheduler"
  ],
  "providers": {
    "strata": {
      "name": "Strata (local)",
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "http://127.0.0.1:8080/v1",
        "apiKey": "none"
      },
      "models": {
        "qwen3.8-flash-next-iq2_xs": {
          "name": "Qwen3.8-Flash-Next (Strata)",
          "limit": {
            "context": 65536,
            "output": 8192
          },
          "settings": {
            "reasoningEffort": "high"
          },
          "variants": [
            { "id": "low", "settings": { "reasoningEffort": "low" } },
            { "id": "medium", "settings": { "reasoningEffort": "medium" } },
            { "id": "none", "settings": { "reasoningEffort": "none" } }
          ]
        },
        "qwen3.8-flash-next-coder-iq1_m": {
          "name": "Qwen3.8-Flash-Next Coder (Strata)",
          "limit": {
            "context": 131072,
            "output": 8192
          },
          "settings": {
            "reasoningEffort": "high"
          },
          "variants": [
            { "id": "low", "settings": { "reasoningEffort": "low" } },
            { "id": "medium", "settings": { "reasoningEffort": "medium" } },
            { "id": "none", "settings": { "reasoningEffort": "none" } }
          ]
        }
      }
    }
  },
  "mcp": {
    "servers": {
      "context7": {
        "type": "remote",
        "url": "https://mcp.context7.com/mcp"
      },
      "videowizard": {
        "type": "local",
        "command": ["npm", "--silent", "--prefix", "{{VIDEOWIZARD_DIR}}", "run", "mcp"]
      },
      "excalidraw": {
        "type": "local",
        "command": [
          "npx",
          "-y",
          "mcp-excalidraw-server"
        ],
        "environment": {
          "EXCALIDRAW_DATA_DIR": "{{HOME}}/.excalidraw-data",
          "EXCALIDRAW_EXPORT_DIR": "{{TMP}}/opencode"
        }
      },
      "clipy": {
        "type": "local",
        "command": [
          "node",
          "{{CLIPY_MCP_ENTRY}}"
        ]
      },
      "rea": {
        "type": "local",
        "command": [
          "cmd.exe",
          "/d",
          "/c",
          "npx",
          "-y",
          "rea-agents@6.7.0",
          "mcp"
        ]
      },
      "craft-anything": {
        "type": "local",
        "command": [
          "{{CRAFT_ANYTHING_CLI}}",
          "mcp"
        ]
      },
      "figma": {
        "type": "local",
        "command": [
          "bun",
          "run",
          "{{FIGMA_SERVER}}"
        ],
        "environment": {
          "FIGMA_WS_URL": "ws://localhost:3055"
        }
      },
      "blender": {
        "type": "local",
        "command": [
          "cmd.exe",
          "/d",
          "/c",
          "uvx",
          "blender-mcp"
        ]
      }
    },
    "diffusion": {
      "type": "remote",
      "enabled": true,
      "url": "http://127.0.0.1:3274/mcp"
    }
  }
}
