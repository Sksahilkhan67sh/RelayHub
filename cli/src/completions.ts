export const COMMAND_NAMES = [
  "login",
  "logout",
  "whoami",
  "projects",
  "endpoints",
  "publish",
  "deliveries",
  "replay",
  "dlq",
  "analytics",
  "insights",
  "billing",
  "notifications",
  "config",
  "version",
  "doctor",
  "completion",
];

function bashScript(): string {
  return `# relay CLI bash completion
# Install: relay completion bash >> ~/.bashrc   (or source it from a completions dir)
_relay_completions() {
  local cur="\${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=( $(compgen -W "${COMMAND_NAMES.join(" ")}" -- "$cur") )
}
complete -F _relay_completions relay
`;
}

function zshScript(): string {
  return `# relay CLI zsh completion
# Install: relay completion zsh >> ~/.zshrc   (or source it from a completions dir)
_relay() {
  local -a commands
  commands=(${COMMAND_NAMES.map((c) => `'${c}'`).join(" ")})
  _describe 'command' commands
}
compdef _relay relay
`;
}

export function completionScript(shell: string): string | null {
  if (shell === "bash") return bashScript();
  if (shell === "zsh") return zshScript();
  return null;
}
