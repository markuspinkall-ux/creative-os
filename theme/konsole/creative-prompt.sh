# Creative OS – Eingabezeile im Graphit-Look (nur interaktive Bash).
# Ein eigenes PS1 in ~/.bashrc hat automatisch Vorrang. Ganz abschalten:
# CREATIVE_PROMPT=0 in ~/.bashrc vor dem Laden von /etc/bashrc setzen.
if [ -n "${BASH_VERSION:-}" ] && [ -n "${PS1:-}" ] && [ "${CREATIVE_PROMPT:-1}" != 0 ] \
   && [ "${TERM:-dumb}" != dumb ] && [ "${TERM:-}" != linux ]; then
    __creative_ps1_start="$PS1"
    __creative_ps1_last=""
    __creative_prompt() {
        local code=$?
        # Eigenes PS1 (z. B. aus ~/.bashrc) hat Vorrang
        if [ "$PS1" != "$__creative_ps1_start" ] && [ "$PS1" != "$__creative_ps1_last" ]; then
            return $code
        fi
        local a='\[\e[38;2;143;179;255m\]' t='\[\e[1;38;2;220;230;255m\]' m='\[\e[38;2;111;122;146m\]'
        local f='\[\e[38;2;255;176;122m\]' r='\[\e[38;2;255;138;142m\]' n='\[\e[0m\]'
        local branch=""
        if command -v git >/dev/null 2>&1; then
            branch=$(git symbolic-ref --short -q HEAD 2>/dev/null || git rev-parse --short -q HEAD 2>/dev/null)
        fi
        local who="$a\\u$m@\\h"
        [ "${EUID:-$(id -u)}" -eq 0 ] && who="$r\\u$m@\\h"
        local arrow="$a›"
        [ "$code" -ne 0 ] && arrow="$r› $code"
        PS1="$who $t\\w$n${branch:+ $f⎇ $branch}$n\n$arrow$n "
        __creative_ps1_last="$PS1"
        __creative_ps1_last="$PS1"
        return $code
    }
    case ";${PROMPT_COMMAND:-};" in
        *";__creative_prompt;"*) ;;
        *) PROMPT_COMMAND="__creative_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
    esac
fi
