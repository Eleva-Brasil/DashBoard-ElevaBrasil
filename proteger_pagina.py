#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protege o dashboard com senha antes de publicar no GitHub Pages.

Pega o HTML final (dashboard_eleva.html), criptografa inteiro com AES-256-GCM
(chave derivada da senha via PBKDF2-SHA256) e gera uma página de login que só
descriptografa no navegador quando a senha certa é digitada. Sem a senha, o
código-fonte publicado não tem nenhum número legível.

A senha vem da variável de ambiente DASHBOARD_SENHA (secret do GitHub Actions).
Se ela não estiver definida, o script FALHA - nunca publica a página aberta.

Uso:
    DASHBOARD_SENHA=... python3 proteger_pagina.py dashboard_eleva.html _site/index.html
"""
import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

BASE = Path(__file__).parent
LOGO_FILE = BASE / "eleva_logo.png"

ITERACOES = 600_000
# Salt fixo (público) para a chave derivada continuar valendo entre uma
# publicação e outra - assim o "manter conectado" não cai a cada atualização
# horária. Trocar a senha invalida automaticamente quem estava conectado.
SALT = hashlib.sha256(b"eleva-dashboard|v1").digest()[:16]


def main():
    if len(sys.argv) != 3:
        sys.exit("Uso: python3 proteger_pagina.py <entrada.html> <saida.html>")
    senha = os.environ.get("DASHBOARD_SENHA", "")
    if not senha:
        sys.exit("DASHBOARD_SENHA não definida - página NÃO publicada (não publicamos sem senha).")

    entrada, saida = Path(sys.argv[1]), Path(sys.argv[2])
    conteudo = entrada.read_bytes()

    chave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=ITERACOES).derive(senha.encode("utf-8"))
    iv = os.urandom(12)
    cifrado = AESGCM(chave).encrypt(iv, conteudo, None)

    b64 = lambda b: base64.b64encode(b).decode()
    logo_b64 = b64(LOGO_FILE.read_bytes())

    pagina = LOGIN_HTML
    for marcador, valor in {
        "__LOGO__": logo_b64,
        "__SALT__": b64(SALT),
        "__IV__": b64(iv),
        "__DADOS__": b64(cifrado),
        "__ITERACOES__": str(ITERACOES),
    }.items():
        pagina = pagina.replace(marcador, valor)

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(pagina, encoding="utf-8")
    print(f"Página protegida gerada em {saida} ({len(pagina) / 1024:.0f} KB).")


LOGIN_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<title>Dashboard Gerencial - Eleva Brasil</title>
<style>
:root{
  --bg-deep:#0a1f3d;
  --bg-deep-2:#0d2a52;
  --card-bg:#ffffff;
  --ink-primary:#0b1220;
  --ink-secondary:#52606d;
  --hairline:#e6e9ee;
  --critical:#d03b3b;
  --neutral:#2a78d6;
}
*{ box-sizing:border-box; }
html,body{ margin:0; min-height:100%; }
body{
  min-height:100vh; display:flex; align-items:center; justify-content:center; padding:16px;
  background:linear-gradient(160deg, var(--bg-deep) 0%, var(--bg-deep-2) 100%);
  font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color:var(--ink-primary);
}
.card{
  width:100%; max-width:360px; background:var(--card-bg); border-radius:14px; padding:32px 28px 26px;
  box-shadow:0 1px 2px rgba(10,20,40,.06), 0 12px 40px rgba(0,0,0,.30);
}
.logo{ display:block; height:48px; width:auto; margin:0 auto 22px; }
h1{ font-size:17px; margin:0 0 4px; text-align:center; }
.sub{ font-size:13px; color:var(--ink-secondary); text-align:center; margin:0 0 22px; }
label.campo{ display:block; font-size:12px; font-weight:600; color:var(--ink-secondary); margin-bottom:6px; }
input[type=password]{
  width:100%; font:inherit; font-size:15px; padding:11px 12px; border:1px solid var(--hairline);
  border-radius:9px; outline:none;
}
input[type=password]:focus{ border-color:var(--neutral); box-shadow:0 0 0 3px rgba(42,120,214,.15); }
.lembrar{ display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink-secondary); margin:14px 0 18px; cursor:pointer; }
button{
  width:100%; font:inherit; font-size:14px; font-weight:600; padding:11px; border:none; border-radius:9px;
  background:var(--bg-deep); color:#fff; cursor:pointer;
}
button:hover{ background:var(--bg-deep-2); }
button:disabled{ opacity:.6; cursor:default; }
.erro{ min-height:18px; font-size:13px; color:var(--critical); text-align:center; margin-top:12px; }
</style>
</head>
<body>
<form class="card" id="form" autocomplete="on">
  <img class="logo" src="data:image/png;base64,__LOGO__" alt="Eleva Brasil"/>
  <h1>Dashboard Gerencial</h1>
  <p class="sub">Acesso restrito. Digite a senha para continuar.</p>
  <input type="text" name="username" value="dashboard-eleva" autocomplete="username" hidden/>
  <label class="campo" for="senha">Senha</label>
  <input type="password" id="senha" autocomplete="current-password" required autofocus/>
  <label class="lembrar"><input type="checkbox" id="lembrar"/> Manter conectado neste aparelho</label>
  <button type="submit" id="entrar">Entrar</button>
  <div class="erro" id="erro" role="alert"></div>
</form>
<script>
(function(){
  var SALT = "__SALT__", IV = "__IV__", DADOS = "__DADOS__", ITERACOES = __ITERACOES__;
  var CHAVE_ARMAZENADA = "eleva-dashboard-chave";

  function b64(s){ var bin = atob(s), out = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out; }
  function paraB64(buf){ var b = new Uint8Array(buf), s = ""; for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return btoa(s); }
  function ler(store){ try { return window[store].getItem(CHAVE_ARMAZENADA); } catch (e) { return null; } }
  function gravar(store, v){ try { window[store].setItem(CHAVE_ARMAZENADA, v); } catch (e) {} }
  function apagar(){ ["localStorage", "sessionStorage"].forEach(function(s){ try { window[s].removeItem(CHAVE_ARMAZENADA); } catch (e) {} }); }

  async function derivar(senha){
    var base = await crypto.subtle.importKey("raw", new TextEncoder().encode(senha), "PBKDF2", false, ["deriveBits"]);
    return crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: b64(SALT), iterations: ITERACOES }, base, 256);
  }

  async function descriptografar(chaveBruta){
    var chave = await crypto.subtle.importKey("raw", chaveBruta, "AES-GCM", false, ["decrypt"]);
    var claro = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(IV) }, chave, b64(DADOS));
    return new TextDecoder().decode(claro);
  }

  function mostrar(html){ document.open(); document.write(html); document.close(); }

  // Já conectado (nesta aba ou "manter conectado")? Tenta abrir direto.
  var salva = ler("sessionStorage") || ler("localStorage");
  if (salva) { descriptografar(b64(salva)).then(mostrar, apagar); }

  var form = document.getElementById("form"), btn = document.getElementById("entrar"), erro = document.getElementById("erro");
  form.addEventListener("submit", async function(ev){
    ev.preventDefault();
    erro.textContent = ""; btn.disabled = true; btn.textContent = "Abrindo...";
    try {
      var bruta = await derivar(document.getElementById("senha").value);
      var html = await descriptografar(bruta);
      var v = paraB64(bruta);
      gravar("sessionStorage", v);
      if (document.getElementById("lembrar").checked) gravar("localStorage", v);
      mostrar(html);
    } catch (e) {
      btn.disabled = false; btn.textContent = "Entrar";
      erro.textContent = "Senha incorreta.";
    }
  });
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
