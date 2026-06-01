from __future__ import annotations

import base64
import os
import uuid
import wave
from dataclasses import asdict
from pathlib import Path

from fastapi import BackgroundTasks, Body, Cookie, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .audio_jobs import cleanup_audio_job, create_audio_job, get_audio_job, render_audio_job
from .midi_fixer import (
    MidiFixOptions,
    fix_midi_bytes,
    list_instrument_family_names,
    list_style_names,
)
from .rendering import list_audio_genres


INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>iMixing — редактор MIDI</title>
  <style>
    :root {
      --bg: #f5efe4;
      --panel: rgba(255, 252, 247, 0.92);
      --ink: #1d2a22;
      --muted: #657069;
      --line: rgba(29, 42, 34, 0.12);
      --accent: #1f6b4f;
      --accent-2: #d68b33;
      --shadow: 0 22px 70px rgba(38, 48, 42, 0.12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(214, 139, 51, 0.22), transparent 28%),
        radial-gradient(circle at right 20%, rgba(31, 107, 79, 0.18), transparent 32%),
        linear-gradient(180deg, #f8f4eb 0%, #efe5d5 100%);
      display: grid;
      place-items: center;
      padding: 24px;
    }

    .shell {
      width: min(960px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
      backdrop-filter: blur(10px);
    }

    .hero {
      padding: 32px 32px 8px;
      background:
        linear-gradient(135deg, rgba(31, 107, 79, 0.1), transparent 40%),
        linear-gradient(225deg, rgba(214, 139, 51, 0.14), transparent 44%);
    }

    .eyebrow {
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 10px;
      font-weight: 700;
    }

    h1 {
      margin: 0 0 10px;
      font-family: "Avenir Next", "Trebuchet MS", sans-serif;
      font-size: clamp(32px, 6vw, 54px);
      line-height: 0.95;
      max-width: 9ch;
    }

    .subtitle {
      margin: 0;
      color: var(--muted);
      max-width: 56ch;
      line-height: 1.5;
    }

    .hero-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
    }

    .credit-badge {
      display: grid;
      gap: 2px;
      min-width: 132px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
      text-align: right;
    }

    .credit-badge strong {
      font-size: 24px;
      line-height: 1;
      color: var(--accent);
    }

    .credit-badge span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .tabs {
      display: flex;
      gap: 10px;
      padding: 18px 32px 0;
      background: rgba(255, 255, 255, 0.28);
    }

    .tab-button {
      box-shadow: none;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      color: var(--muted);
      padding: 11px 14px;
      border-radius: 14px;
    }

    .tab-button.active {
      background: var(--accent);
      border-color: transparent;
      color: white;
    }

    .panel {
      display: none;
    }

    .panel.active {
      display: block;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.25fr 0.85fr;
      gap: 22px;
      padding: 24px 32px 32px;
    }

    .card {
      background: rgba(255, 255, 255, 0.75);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
    }

    .dropzone {
      border: 2px dashed rgba(31, 107, 79, 0.32);
      border-radius: 20px;
      min-height: 240px;
      padding: 24px;
      display: grid;
      place-items: center;
      text-align: center;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
      background:
        linear-gradient(180deg, rgba(31, 107, 79, 0.04), rgba(214, 139, 51, 0.05));
      cursor: pointer;
    }

    .dropzone.drag {
      transform: translateY(-2px);
      border-color: var(--accent-2);
      background:
        linear-gradient(180deg, rgba(214, 139, 51, 0.08), rgba(31, 107, 79, 0.08));
    }

    .drop-title {
      font-size: 24px;
      font-weight: 700;
      margin: 12px 0 6px;
    }

    .drop-copy {
      color: var(--muted);
      margin: 0 auto;
      max-width: 34ch;
      line-height: 1.45;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(31, 107, 79, 0.08);
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
    }

    .alert-banner {
      display: grid;
      gap: 6px;
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(214, 139, 51, 0.22);
      background:
        linear-gradient(180deg, rgba(214, 139, 51, 0.12), rgba(255, 255, 255, 0.88));
    }

    .alert-label {
      display: inline-flex;
      width: fit-content;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(214, 139, 51, 0.16);
      color: #8a5310;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .alert-banner strong {
      font-size: 18px;
      line-height: 1.15;
    }

    .alert-banner span {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.42;
    }

    .controls {
      display: grid;
      gap: 14px;
    }

    .family-group {
      display: grid;
      gap: 10px;
    }

    .family-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
    }

    .family-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .family-chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 13px;
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
      line-height: 1;
      cursor: pointer;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease, color 140ms ease;
    }

    .family-chip:hover:not(:disabled) {
      transform: translateY(-1px);
      border-color: rgba(31, 107, 79, 0.28);
      background: rgba(31, 107, 79, 0.06);
    }

    .family-chip.active {
      border-color: rgba(31, 107, 79, 0.3);
      background: linear-gradient(135deg, rgba(31, 107, 79, 0.16), rgba(31, 107, 79, 0.06));
      color: var(--accent);
    }

    .family-chip:disabled {
      cursor: not-allowed;
      color: rgba(29, 42, 34, 0.48);
      background: rgba(29, 42, 34, 0.04);
    }

    .family-copy {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.42;
    }

    label {
      display: grid;
      gap: 8px;
      font-size: 14px;
      font-weight: 600;
    }

    select, button {
      font: inherit;
    }

    select {
      width: 100%;
      padding: 14px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
    }

    .checkbox {
      display: flex;
      gap: 10px;
      align-items: center;
      color: var(--muted);
      font-weight: 500;
    }

    .checkbox input {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
    }

    button {
      border: 0;
      border-radius: 16px;
      padding: 15px 18px;
      background: linear-gradient(135deg, var(--accent), #2d8d68);
      color: white;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 16px 24px rgba(31, 107, 79, 0.18);
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
      box-shadow: none;
    }

    .status {
      min-height: 24px;
      color: var(--muted);
      font-size: 14px;
    }

    .stats {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }

    .stat {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(29, 42, 34, 0.04);
      font-size: 14px;
    }

    .stat strong {
      font-weight: 700;
    }

    .hint {
      margin-top: 16px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .hint strong {
      color: var(--ink);
    }

    .file-list {
      display: grid;
      gap: 8px;
      margin-top: 14px;
      color: var(--muted);
      font-size: 13px;
    }

    .file-item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 11px;
      border-radius: 12px;
      background: rgba(29, 42, 34, 0.04);
    }

    .preview {
      display: none;
      gap: 12px;
      margin-top: 16px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.62);
    }

    .preview.active {
      display: grid;
    }

    .preview-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 14px;
      font-weight: 700;
    }

    .preview-title span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }

    audio {
      width: 100%;
    }

    .secondary-button {
      box-shadow: none;
      border: 1px solid var(--line);
      background: white;
      color: var(--accent);
      padding: 11px 14px;
      border-radius: 14px;
    }

    .preview-actions {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }

    .pricing-intro {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      padding: 24px 32px 0;
      align-items: start;
    }

    .pricing-intro h2 {
      margin: 10px 0 10px;
      font-size: clamp(28px, 4vw, 40px);
      line-height: 0.98;
      max-width: 16ch;
    }

    .pricing-intro p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 58ch;
    }

    .pricing-note {
      display: grid;
      gap: 8px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background:
        linear-gradient(135deg, rgba(31, 107, 79, 0.08), rgba(214, 139, 51, 0.08)),
        rgba(255, 255, 255, 0.76);
    }

    .pricing-note strong {
      font-size: 16px;
      line-height: 1.2;
    }

    .pricing-note span {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .pricing-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      padding: 24px 32px 14px;
    }

    .price-card {
      display: grid;
      gap: 12px;
      align-content: start;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      background: rgba(255, 255, 255, 0.72);
    }

    .price-card.featured {
      border-color: rgba(31, 107, 79, 0.34);
      box-shadow: 0 18px 45px rgba(31, 107, 79, 0.1);
    }

    .price-kicker {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .price-card h2 {
      margin: 0;
      font-size: 20px;
    }

    .price {
      font-size: 28px;
      font-weight: 800;
      color: var(--accent);
    }

    .price-copy {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }

    .price-meta {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      margin-top: -4px;
    }

    .price-card ul {
      display: grid;
      gap: 8px;
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }

    .price-card button {
      margin-top: auto;
    }

    .credit-panel {
      margin: 0 32px 32px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
    }

    .pricing-detail-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
      align-items: start;
    }

    .pricing-demo {
      display: grid;
      gap: 14px;
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
    }

    .topup-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }

    .topup-card {
      display: grid;
      gap: 8px;
      padding: 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(29, 42, 34, 0.04);
    }

    .topup-card strong {
      font-size: 14px;
      line-height: 1.15;
    }

    .topup-price {
      font-size: 24px;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
    }

    .topup-copy {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.42;
    }

    .credit-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }

    .info {
      display: grid;
      gap: 18px;
      padding: 0 32px 34px;
    }

    .section {
      border-top: 1px solid var(--line);
      padding-top: 22px;
    }

    .section h2 {
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.15;
    }

    .section p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }

    .steps,
    .features,
    .styles {
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }

    .steps {
      grid-template-columns: repeat(4, 1fr);
    }

    .features,
    .styles {
      grid-template-columns: repeat(3, 1fr);
    }

    .mini-card {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 15px;
      background: rgba(255, 255, 255, 0.62);
    }

    .mini-card strong {
      display: block;
      margin-bottom: 6px;
      font-size: 14px;
    }

    .mini-card span {
      display: block;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.42;
    }

    .result-list {
      display: grid;
      gap: 8px;
      margin: 14px 0 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      line-height: 1.45;
    }

    .result-list li {
      position: relative;
      padding-left: 18px;
    }

    .result-list li::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0.65em;
      width: 7px;
      height: 7px;
      border-radius: 99px;
      background: var(--accent-2);
    }

    input[type="file"] {
      display: none;
    }

    /* Design 1.0 layout, dark glass visual refresh */
    :root {
      --bg: #030509;
      --panel: rgba(10, 13, 22, 0.72);
      --ink: #f8f8ff;
      --muted: rgba(248, 248, 255, 0.68);
      --line: rgba(255, 255, 255, 0.14);
      --accent: #eaf7ff;
      --accent-2: #7be7ff;
      --glow-pink: rgba(255, 78, 146, 0.22);
      --glow-cyan: rgba(87, 214, 255, 0.18);
      --shadow: 0 28px 110px rgba(0, 0, 0, 0.56);
    }

    body {
      background:
        radial-gradient(circle at 22% 10%, var(--glow-pink), transparent 30%),
        radial-gradient(circle at 82% 18%, var(--glow-cyan), transparent 28%),
        radial-gradient(circle at 50% 110%, rgba(125, 255, 214, 0.08), transparent 36%),
        linear-gradient(180deg, #05060b 0%, #020307 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 80px 80px;
      mask-image: radial-gradient(circle at 50% 24%, black, transparent 74%);
      opacity: 0.22;
    }

    .shell {
      position: relative;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.045)),
        var(--panel);
      border-color: rgba(255, 255, 255, 0.16);
      box-shadow: var(--shadow), inset 0 1px 0 rgba(255,255,255,0.1);
      backdrop-filter: blur(22px);
    }

    .shell::before {
      content: "";
      position: absolute;
      inset: -1px;
      pointer-events: none;
      background:
        radial-gradient(circle at 28% 0%, rgba(255, 78, 146, 0.18), transparent 34%),
        radial-gradient(circle at 82% 10%, rgba(87, 214, 255, 0.16), transparent 34%);
      opacity: 0.9;
    }

    .shell > * {
      position: relative;
      z-index: 1;
    }

    .hero {
      background:
        radial-gradient(circle at 18% 5%, rgba(255, 78, 146, 0.18), transparent 36%),
        radial-gradient(circle at 86% 18%, rgba(87, 214, 255, 0.14), transparent 34%),
        linear-gradient(180deg, rgba(255,255,255,0.045), transparent);
    }

    h1 {
      color: var(--ink);
      text-shadow: 0 0 42px rgba(255, 255, 255, 0.12);
    }

    .eyebrow,
    .price,
    .topup-price,
    .secondary-button {
      color: var(--accent-2);
    }

    .subtitle,
    .drop-copy,
    .family-copy,
    .checkbox,
    .status,
    .hint,
    .file-list,
    .preview-title span,
    .pricing-intro p,
    .pricing-note span,
    .price-copy,
    .price-meta,
    .price-card ul,
    .topup-copy,
    .section p,
    .mini-card span,
    .result-list,
    .alert-banner span,
    .price-kicker {
      color: var(--muted);
    }

    .credit-badge,
    .card,
    .preview,
    .pricing-note,
    .price-card,
    .credit-panel,
    .mini-card,
    .topup-card {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.105), rgba(255,255,255,0.045));
      border-color: rgba(255,255,255,0.14);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
      backdrop-filter: blur(18px);
    }

    .tabs {
      background: rgba(255,255,255,0.035);
    }

    .tab-button,
    .family-chip,
    .secondary-button {
      background: rgba(255,255,255,0.07);
      border-color: rgba(255,255,255,0.14);
      color: rgba(248,248,255,0.72);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
    }

    .tab-button.active,
    .family-chip.active {
      color: #05070c;
      background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(220,246,255,0.86));
      border-color: rgba(255,255,255,0.5);
      box-shadow: 0 16px 42px rgba(87,214,255,0.12);
    }

    .family-chip:hover:not(:disabled) {
      border-color: rgba(123,231,255,0.38);
      background: rgba(123,231,255,0.09);
    }

    .family-chip:disabled {
      color: rgba(248,248,255,0.32);
      background: rgba(255,255,255,0.035);
    }

    .dropzone {
      border-color: rgba(123,231,255,0.28);
      background:
        radial-gradient(circle at 35% 20%, rgba(255, 78, 146, 0.12), transparent 34%),
        radial-gradient(circle at 70% 80%, rgba(87, 214, 255, 0.12), transparent 34%),
        rgba(255,255,255,0.035);
    }

    .dropzone.drag {
      border-color: rgba(255,255,255,0.52);
      background:
        radial-gradient(circle at 35% 20%, rgba(255, 78, 146, 0.18), transparent 34%),
        radial-gradient(circle at 70% 80%, rgba(87, 214, 255, 0.18), transparent 34%),
        rgba(255,255,255,0.055);
    }

    .pill,
    .alert-label {
      color: var(--accent-2);
      background: rgba(123,231,255,0.09);
      border: 1px solid rgba(123,231,255,0.16);
    }

    .alert-banner {
      border-color: rgba(255, 78, 146, 0.22);
      background:
        radial-gradient(circle at 0% 0%, rgba(255, 78, 146, 0.12), transparent 48%),
        rgba(255,255,255,0.055);
    }

    select {
      background: rgba(255,255,255,0.08);
      color: var(--ink);
      border-color: rgba(255,255,255,0.14);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
    }

    select option {
      background: #0b0d14;
      color: var(--ink);
    }

    button {
      background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(220,246,255,0.88));
      color: #05070c;
      box-shadow: 0 18px 48px rgba(87,214,255,0.13), 0 2px 0 rgba(255,255,255,0.16) inset;
    }

    button:hover:not(:disabled),
    .secondary-button:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 22px 58px rgba(255,78,146,0.12), 0 18px 48px rgba(87,214,255,0.13);
    }

    .secondary-button {
      background: rgba(255,255,255,0.07);
    }

    .stat,
    .file-item {
      background: rgba(255,255,255,0.055);
      border: 1px solid rgba(255,255,255,0.08);
    }

    .section {
      border-top-color: rgba(255,255,255,0.12);
    }

    .result-list li::before {
      background: var(--accent-2);
      box-shadow: 0 0 18px rgba(123,231,255,0.34);
    }

    .price-card.featured {
      border-color: rgba(123,231,255,0.26);
      box-shadow: 0 22px 70px rgba(87,214,255,0.1), inset 0 1px 0 rgba(255,255,255,0.1);
    }

    audio {
      filter: saturate(0.9);
    }

    /* Remove flat grey haze: darker base with soft colored glow */
    .shell {
      background:
        radial-gradient(circle at 8% 4%, rgba(255, 78, 146, 0.18), transparent 34%),
        radial-gradient(circle at 92% 6%, rgba(87, 214, 255, 0.16), transparent 34%),
        linear-gradient(180deg, rgba(15, 17, 29, 0.84), rgba(7, 9, 16, 0.88));
    }

    .hero {
      background:
        radial-gradient(circle at 16% 10%, rgba(255, 78, 146, 0.24), transparent 36%),
        radial-gradient(circle at 92% 8%, rgba(87, 214, 255, 0.18), transparent 34%),
        linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012));
    }

    .card,
    .preview,
    .pricing-note,
    .price-card,
    .credit-panel,
    .mini-card,
    .topup-card {
      background:
        radial-gradient(circle at 18% 0%, rgba(255, 78, 146, 0.08), transparent 38%),
        radial-gradient(circle at 100% 0%, rgba(87, 214, 255, 0.075), transparent 36%),
        linear-gradient(180deg, rgba(255,255,255,0.082), rgba(255,255,255,0.032));
    }

    .tabs {
      background:
        linear-gradient(90deg, rgba(255,78,146,0.05), rgba(87,214,255,0.045)),
        rgba(4, 6, 12, 0.22);
      border-top: 1px solid rgba(255,255,255,0.06);
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }

    .credit-badge {
      background:
        radial-gradient(circle at 100% 0%, rgba(87,214,255,0.13), transparent 44%),
        rgba(255,255,255,0.075);
    }

    /* Minimal black/red theme: no gradients, no shadows */
    :root {
      --bg: #050505;
      --panel: rgba(255, 255, 255, 0.035);
      --ink: #f5f2f2;
      --muted: rgba(245, 242, 242, 0.62);
      --line: rgba(255, 255, 255, 0.13);
      --accent: #ff2d2d;
      --accent-2: #ff2d2d;
      --shadow: none;
    }

    body {
      background: #050505;
      color: var(--ink);
    }

    body::before,
    .shell::before {
      display: none;
    }

    .shell,
    .hero,
    .tabs,
    .credit-badge,
    .card,
    .dropzone,
    .preview,
    .pricing-note,
    .price-card,
    .credit-panel,
    .mini-card,
    .topup-card,
    .alert-banner,
    .stat,
    .file-item {
      background: rgba(255, 255, 255, 0.035);
      box-shadow: none;
      text-shadow: none;
    }

    .shell {
      border: 1px solid rgba(255, 255, 255, 0.14);
      backdrop-filter: blur(18px);
    }

    .hero {
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    h1,
    .alert-banner strong,
    .family-title,
    .hint strong,
    .price-card h2,
    .section h2,
    .mini-card strong,
    .topup-card strong {
      color: var(--ink);
      text-shadow: none;
    }

    .eyebrow,
    .credit-badge strong,
    .pill,
    .alert-label,
    .price,
    .topup-price,
    .secondary-button,
    .result-list li::before {
      color: var(--accent);
    }

    .pill,
    .alert-label {
      background: rgba(255, 45, 45, 0.08);
      border: 1px solid rgba(255, 45, 45, 0.22);
    }

    .tabs {
      border-top: 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .tab-button,
    .family-chip,
    .secondary-button,
    select {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.14);
      color: var(--ink);
      box-shadow: none;
    }

    .tab-button.active,
    .family-chip.active {
      background: var(--accent);
      border-color: var(--accent);
      color: #050505;
      box-shadow: none;
    }

    .family-chip:hover:not(:disabled),
    .tab-button:hover:not(:disabled),
    .secondary-button:hover:not(:disabled) {
      background: rgba(255, 45, 45, 0.08);
      border-color: rgba(255, 45, 45, 0.42);
      color: var(--ink);
      transform: none;
      box-shadow: none;
    }

    .tab-button.active:hover:not(:disabled),
    .family-chip.active:hover:not(:disabled) {
      background: var(--accent);
      color: #050505;
    }

    .dropzone {
      border: 1px dashed rgba(255, 45, 45, 0.42);
    }

    .dropzone.drag {
      background: rgba(255, 45, 45, 0.06);
      border-color: var(--accent);
      transform: none;
    }

    button {
      background: var(--accent);
      color: #050505;
      box-shadow: none;
    }

    button:hover:not(:disabled) {
      background: #ff4a4a;
      color: #050505;
      transform: none;
      box-shadow: none;
    }

    button:disabled {
      opacity: 0.45;
      box-shadow: none;
    }

    .secondary-button {
      background: transparent;
      color: var(--accent);
    }

    .secondary-button:hover:not(:disabled) {
      color: var(--accent);
    }

    .price-card.featured {
      border-color: rgba(255, 45, 45, 0.42);
      box-shadow: none;
    }

    .result-list li::before {
      background: var(--accent);
      box-shadow: none;
    }

    /* Modern music-tech typography */
    body {
      font-family: Inter, "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.55;
      letter-spacing: -0.012em;
      font-feature-settings: "kern", "liga", "tnum";
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }

    h1 {
      max-width: 11.4ch;
      margin-bottom: 16px;
      font-family: "SF Pro Display", Inter, "Avenir Next", "Segoe UI", sans-serif;
      font-size: clamp(42px, 5.9vw, 64px);
      font-weight: 760;
      line-height: 0.96;
      letter-spacing: -0.044em;
    }

    .subtitle {
      max-width: 48ch;
      font-size: 16px;
      line-height: 1.62;
      letter-spacing: -0.018em;
    }

    .eyebrow,
    .pill,
    .alert-label,
    .credit-badge span,
    .tab-button,
    .family-chip,
    label,
    button,
    .secondary-button,
    .price-meta,
    .price-kicker,
    .stat,
    .file-item,
    .preview-title span {
      font-family: "SF Mono", "Roboto Mono", "JetBrains Mono", ui-monospace, monospace;
      letter-spacing: 0.015em;
    }

    .tab-button,
    .family-chip,
    label,
    button,
    .secondary-button {
      font-family: Inter, "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: -0.012em;
    }

    .eyebrow {
      font-size: 11px;
      letter-spacing: 0.18em;
      line-height: 1;
    }

    .tab-button,
    button,
    .secondary-button {
      font-size: 13px;
      font-weight: 760;
    }

    .family-chip,
    label {
      font-size: 12px;
      font-weight: 720;
    }

    .drop-title {
      font-size: clamp(22px, 3vw, 30px);
      line-height: 1.04;
      letter-spacing: -0.04em;
      font-weight: 760;
    }

    .drop-copy,
    .family-copy,
    .hint,
    .status,
    .result-list,
    .price-copy,
    .topup-copy,
    .section p,
    .mini-card span,
    .alert-banner span {
      font-size: 14px;
      line-height: 1.58;
      letter-spacing: -0.01em;
    }

    .alert-banner strong,
    .pricing-intro h2,
    .section h2 {
      font-family: "SF Pro Display", Inter, "Avenir Next", "Segoe UI", sans-serif;
      letter-spacing: -0.045em;
    }

    .alert-banner strong {
      font-size: 19px;
      line-height: 1.08;
      font-weight: 760;
    }

    .pricing-intro h2 {
      font-size: clamp(30px, 4.2vw, 46px);
      line-height: 0.96;
      font-weight: 780;
    }

    .section h2 {
      font-size: clamp(24px, 3vw, 32px);
      line-height: 1.04;
      font-weight: 760;
    }

    .credit-badge strong,
    .price,
    .topup-price {
      font-family: "SF Pro Display", Inter, "Avenir Next", "Segoe UI", sans-serif;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.055em;
    }

    .credit-badge strong {
      font-size: 28px;
      font-weight: 820;
    }

    .price {
      font-size: 34px;
      line-height: 0.94;
      font-weight: 820;
    }

    select {
      font-size: 14px;
      font-weight: 650;
      letter-spacing: -0.01em;
    }

    /* Solid black / white / red editorial pass */
    :root {
      --bg: #000000;
      --panel: #0b0b0b;
      --surface: #111111;
      --surface-2: #151515;
      --ink: #f7f7f7;
      --muted: #9b9b9b;
      --line: #2a2a2a;
      --line-strong: #3a3a3a;
      --accent: #f03232;
      --accent-2: #f03232;
      --shadow: none;
    }

    body {
      padding: 40px;
      background: #000;
      color: var(--ink);
    }

    .shell,
    .hero,
    .tabs,
    .credit-badge,
    .card,
    .dropzone,
    .preview,
    .pricing-note,
    .price-card,
    .credit-panel,
    .mini-card,
    .topup-card,
    .alert-banner,
    .stat,
    .file-item,
    .tab-button,
    .family-chip,
    .secondary-button,
    select,
    button {
      background-image: none;
      box-shadow: none;
      backdrop-filter: none;
      text-shadow: none;
    }

    .shell {
      width: min(1120px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 30px;
    }

    .hero {
      padding: 58px 56px 34px;
      background: #0b0b0b;
      border-bottom: 1px solid var(--line);
    }

    .hero-top {
      gap: 48px;
    }

    h1 {
      max-width: 12.5ch;
      margin-bottom: 22px;
      color: var(--ink);
      font-size: clamp(48px, 5.4vw, 76px);
      line-height: 0.98;
      letter-spacing: -0.048em;
    }

    .subtitle {
      max-width: 58ch;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.72;
    }

    .eyebrow {
      margin-bottom: 18px;
      color: var(--accent);
    }

    .credit-badge {
      min-width: 156px;
      padding: 20px 22px;
      background: #111;
      border: 1px solid var(--line-strong);
      border-radius: 20px;
    }

    .credit-badge strong {
      color: var(--accent);
    }

    .tabs {
      gap: 12px;
      padding: 28px 56px 0;
      background: #0b0b0b;
      border-bottom: 1px solid var(--line);
    }

    .tab-button,
    .family-chip,
    .secondary-button {
      padding: 13px 18px;
      background: #0b0b0b;
      border: 1px solid var(--line-strong);
      color: var(--ink);
      border-radius: 16px;
    }

    .tab-button.active,
    .family-chip.active,
    button {
      background: var(--accent);
      border-color: var(--accent);
      color: #000;
    }

    .tab-button:hover:not(:disabled),
    .family-chip:hover:not(:disabled),
    .secondary-button:hover:not(:disabled) {
      background: #151515;
      border-color: var(--accent);
      color: var(--ink);
    }

    .tab-button.active:hover:not(:disabled),
    .family-chip.active:hover:not(:disabled),
    button:hover:not(:disabled) {
      background: #ff4a4a;
      border-color: #ff4a4a;
      color: #000;
    }

    .grid {
      gap: 30px;
      padding: 40px 56px 58px;
    }

    .card,
    .preview,
    .pricing-note,
    .price-card,
    .credit-panel,
    .mini-card,
    .topup-card,
    .alert-banner {
      background: var(--surface);
      border: 1px solid var(--line);
    }

    .card {
      padding: 30px;
      border-radius: 24px;
    }

    .dropzone {
      min-height: 310px;
      padding: 36px;
      background: #0b0b0b;
      border: 1px dashed var(--line-strong);
      border-radius: 22px;
    }

    .dropzone.drag {
      background: #111;
      border-color: var(--accent);
    }

    .drop-title {
      margin-top: 16px;
      margin-bottom: 12px;
      color: var(--ink);
    }

    .drop-copy,
    .family-copy,
    .hint,
    .status,
    .result-list,
    .price-copy,
    .topup-copy,
    .section p,
    .mini-card span,
    .alert-banner span,
    .price-card ul,
    .price-meta,
    .file-list,
    .checkbox {
      color: var(--muted);
    }

    .pill,
    .alert-label {
      background: #151515;
      border: 1px solid var(--line-strong);
      color: var(--accent);
    }

    .alert-banner {
      padding: 22px;
      border-color: #3a2222;
    }

    select {
      background: #0b0b0b;
      border: 1px solid var(--line-strong);
      color: var(--ink);
    }

    .stat,
    .file-item {
      background: #0b0b0b;
      border: 1px solid var(--line);
    }

    .section {
      padding-top: 34px;
      border-top: 1px solid var(--line);
    }

    .info {
      gap: 30px;
      padding: 0 56px 58px;
    }

    .steps,
    .features,
    .styles {
      gap: 16px;
      margin-top: 22px;
    }

    .mini-card {
      padding: 22px;
    }

    .pricing-intro {
      gap: 28px;
      padding: 40px 56px 0;
    }

    .pricing-grid {
      gap: 18px;
      padding: 34px 56px 22px;
    }

    .price-card {
      gap: 16px;
      padding: 24px;
      border-radius: 20px;
    }

    .price-card.featured {
      border-color: var(--accent);
    }

    .credit-panel {
      margin: 0 56px 58px;
      padding: 28px;
      border-radius: 22px;
    }

    .topup-card {
      background: #0b0b0b;
    }

    .preview {
      padding: 20px;
    }

    .preview-actions,
    .credit-actions {
      gap: 12px;
    }

    @media (max-width: 780px) {
      body {
        padding: 18px;
      }

      .shell {
        border-radius: 24px;
      }

      .hero {
        padding: 38px 24px 28px;
      }

      .hero-top {
        gap: 28px;
      }

      h1 {
        font-size: clamp(42px, 13vw, 58px);
        max-width: 11.5ch;
      }

      .tabs,
      .grid,
      .info,
      .pricing-intro,
      .pricing-grid {
        padding-left: 24px;
        padding-right: 24px;
      }

      .grid {
        padding-top: 28px;
        padding-bottom: 34px;
      }

      .card {
        padding: 24px;
      }

      .credit-panel {
        margin: 0 24px 34px;
        padding: 24px;
      }
    }

    @media (max-width: 780px) {
      .grid {
        grid-template-columns: 1fr;
        padding: 18px;
      }

      .hero {
        padding: 24px 20px 6px;
      }

      .hero-top {
        display: grid;
      }

      .credit-badge {
        text-align: left;
      }

      .tabs {
        padding: 16px 18px 0;
        flex-direction: column;
      }

      .card {
        padding: 18px;
      }

      .info {
        padding: 0 18px 24px;
      }

      .steps,
      .features,
      .styles {
        grid-template-columns: 1fr;
      }

      .preview-actions {
        grid-template-columns: 1fr;
      }

      .pricing-intro {
        grid-template-columns: 1fr;
        padding: 18px 18px 0;
      }

      .pricing-intro h2 {
        max-width: none;
      }

      .pricing-grid {
        grid-template-columns: 1fr;
        padding: 18px;
      }

      .pricing-detail-grid,
      .topup-grid {
        grid-template-columns: 1fr;
      }

      .credit-panel {
        margin: 0 18px 24px;
      }
    }

    /* Final spacing guard after legacy responsive rules */
    @media (max-width: 780px) {
      body {
        padding: 18px;
      }

      .hero {
        padding: 40px 24px 30px;
      }

      .hero-top {
        gap: 30px;
      }

      .tabs {
        gap: 12px;
        padding: 24px 24px 0;
      }

      .grid {
        gap: 24px;
        padding: 30px 24px 38px;
      }

      .card {
        padding: 24px;
      }

      .info {
        gap: 24px;
        padding: 0 24px 38px;
      }

      .pricing-intro,
      .pricing-grid {
        padding-left: 24px;
        padding-right: 24px;
      }

      .credit-panel {
        margin: 0 24px 38px;
      }
    }

    /* Language-ready typography and lighter mode navigation */
    body {
      font-family: "IBM Plex Sans", "Noto Sans", "Manrope", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }

    h1,
    .pricing-intro h2,
    .section h2,
    .alert-banner strong,
    .drop-title {
      font-family: "IBM Plex Sans", "Noto Sans", "Manrope", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }

    .eyebrow,
    .pill,
    .alert-label,
    .credit-badge span,
    .tab-index,
    .tab-meta,
    .language-button,
    .price-meta,
    .stat {
      font-family: "IBM Plex Mono", "Noto Sans Mono", "SF Mono", "Roboto Mono", ui-monospace, monospace;
    }

    .hero-side {
      display: grid;
      gap: 14px;
      justify-items: end;
    }

    .language-switch {
      display: inline-flex;
      gap: 0;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #000;
    }

    .language-button {
      min-height: 30px;
      padding: 0 11px;
      border: 0;
      border-radius: 999px;
      background: #000;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      box-shadow: none;
    }

    .language-button.active {
      background: var(--ink);
      color: #000;
    }

    .tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0;
      padding: 0 56px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }

    .tab-button {
      position: relative;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 3px 14px;
      align-items: start;
      min-height: 94px;
      padding: 24px 26px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      background: #0b0b0b;
      color: var(--muted);
      text-align: left;
    }

    .tab-button:first-child {
      border-left: 1px solid var(--line);
    }

    .tab-button::after {
      content: "";
      position: absolute;
      left: 26px;
      right: 26px;
      bottom: -1px;
      height: 2px;
      background: transparent;
    }

    .tab-button.active,
    .tab-button.active:hover:not(:disabled) {
      background: #0b0b0b;
      border-color: var(--line);
      color: var(--ink);
    }

    .tab-button.active::after {
      background: var(--accent);
    }

    .tab-button:hover:not(:disabled) {
      background: #111;
      border-color: var(--line);
      color: var(--ink);
    }

    .tab-index {
      grid-row: span 2;
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding-top: 3px;
    }

    .tab-label {
      color: inherit;
      font-size: 17px;
      font-weight: 720;
      letter-spacing: -0.025em;
      line-height: 1.1;
    }

    .tab-meta {
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
      line-height: 1.35;
      text-transform: uppercase;
    }

    @media (max-width: 780px) {
      .hero-side {
        justify-items: start;
      }

      .tabs {
        grid-template-columns: 1fr;
        padding: 0 24px;
      }

      .tab-button,
      .tab-button:first-child {
        min-height: auto;
        padding: 18px 0;
        border-left: 0;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .tab-button::after {
        left: 0;
        right: auto;
        top: 18px;
        bottom: 18px;
        width: 2px;
        height: auto;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="eyebrow" data-i18n="hero.eyebrow">iMixing · редактор MIDI</div>
          <h1 data-i18n="hero.title">Правим MIDI так, чтобы он звучал собранно.</h1>
          <p class="subtitle" data-i18n="hero.subtitle">
            Загрузите MIDI для музыкального исправления или WAV-дорожки для быстрого сведения и мастеринга. Сервис обработает материал и отдаст готовый файл обратно.
          </p>
        </div>
        <div class="hero-side">
          <div class="language-switch" aria-label="Language">
            <button class="language-button active" type="button" data-lang="ru">RU</button>
            <button class="language-button" type="button" data-lang="en">EN</button>
          </div>
          <div class="credit-badge" aria-label="Demo credit balance">
            <strong id="creditBalance">0</strong>
            <span data-i18n="credits.label">демо-баллы</span>
          </div>
        </div>
      </div>
    </section>

    <nav class="tabs" aria-label="Режим сервиса">
      <button class="tab-button active" type="button" data-tab="midiPanel">
        <span class="tab-index">01</span>
        <span class="tab-label" data-i18n="tabs.midi">Редактор MIDI</span>
        <span class="tab-meta" data-i18n="tabs.midiMeta">правка · гармония · экспорт</span>
      </button>
      <button class="tab-button" type="button" data-tab="audioPanel">
        <span class="tab-index">02</span>
        <span class="tab-label" data-i18n="tabs.audio">Сведение и мастеринг</span>
        <span class="tab-meta" data-i18n="tabs.audioMeta">дорожки · LUFS · мастер WAV</span>
      </button>
      <button class="tab-button" type="button" data-tab="pricingPanel">
        <span class="tab-index">03</span>
        <span class="tab-label" data-i18n="tabs.pricing">Тарифы</span>
        <span class="tab-meta" data-i18n="tabs.pricingMeta">баллы · планы · лимиты</span>
      </button>
    </nav>

    <section class="panel active" id="midiPanel">
    <section class="grid">
      <div class="card">
        <div class="pill" data-i18n="midi.pill">Перетащить · исправить · скачать</div>
        <div class="alert-banner" role="note" aria-label="Ограничение по drum MIDI">
          <div class="alert-label" data-i18n="midi.drumsLabel">Барабаны позже</div>
          <strong data-i18n="midi.drumsTitle">Барабанные MIDI пока лучше не загружать в этот режим.</strong>
          <span data-i18n="midi.drumsCopy">Для барабанных партий нужен отдельный режим с другой логикой грува, силы ударов, тихих нот и раскладки по пэдам.</span>
        </div>
        <label class="dropzone" id="dropzone" for="fileInput">
          <input id="fileInput" type="file" accept=".mid,.midi,audio/midi,audio/x-midi">
          <div>
              <div class="drop-title" id="fileTitle" data-i18n="midi.dropTitle">Перетащите `.mid` сюда</div>
              <p class="drop-copy" id="fileCopy" data-i18n="midi.dropCopy">Или нажмите, чтобы выбрать файл. Лучше всего подходят обычные MIDI-партии из нотного редактора без редких служебных событий.</p>
          </div>
        </label>
      </div>

      <div class="card">
        <div class="controls">
          <div class="family-group" aria-label="Тип партии">
            <div class="family-title" data-i18n="midi.familyTitle">Тип партии</div>
            <div class="family-chips">
              <button class="family-chip active" type="button" data-family="harmony" data-i18n="family.harmony">Гармония</button>
              <button class="family-chip" type="button" data-family="keys" data-i18n="family.keys">Клавиши</button>
              <button class="family-chip" type="button" data-family="melody" data-i18n="family.melody">Мелодия</button>
              <button class="family-chip" type="button" disabled aria-disabled="true" data-i18n="family.drumsSoon">Барабаны · скоро</button>
            </div>
            <div class="family-copy" id="familyCopy">
              Гармония подходит для аккордов, пэдов, многоголосных партий и общих гармонических MIDI-фрагментов.
            </div>
          </div>

          <label>
            <span data-i18n="midi.styleLabel">Музыкальный стиль</span>
            <select id="style">
              <option value="balanced" data-i18n="style.balanced">Сбалансированный</option>
              <option value="piano" data-i18n="style.piano">Фортепиано</option>
              <option value="classical" data-i18n="style.classical">Классика</option>
              <option value="jazz" data-i18n="style.jazz">Джаз</option>
              <option value="pop" data-i18n="style.pop">Поп</option>
            </select>
          </label>

          <label>
            <span data-i18n="midi.formatLabel">Формат вывода</span>
            <select id="outputFormat">
              <option value="1" data-i18n="format.ableton">Совместимый формат 1</option>
              <option value="0" data-i18n="format.plain">Простой MIDI, формат 0</option>
            </select>
          </label>

          <label class="checkbox">
            <input id="includeTitles" type="checkbox">
            <span data-i18n="midi.includeTitles">Добавлять названия треков в MIDI</span>
          </label>

          <button id="submitButton" type="button" data-i18n="midi.submit">Исправить и скачать</button>
          <div class="status" id="status" data-i18n="midi.statusEmpty">Файл ещё не выбран.</div>
        </div>

        <div class="stats" id="stats"></div>
        <p class="hint" data-i18n="midi.hint">
          Для большинства секвенсоров лучше оставить совместимый формат 1. Если программа всё равно открывает файл некорректно, попробуйте простой MIDI, формат 0. Для фортепианных партий обычно лучше стиль «Фортепиано», для плотных аккордов — «Джаз». Барабанные MIDI пока лучше не загружать: для них нужен отдельный режим.
        </p>
      </div>
    </section>

    <section class="info" aria-label="Описание сервиса">
      <div class="section">
        <h2 data-i18n="info.whatTitle">Что делает сервис</h2>
        <p data-i18n="info.whatCopy">
          Редактор MIDI принимает файл, разбирает ноты и музыкальную структуру, исправляет неаккуратный тайминг, слишком плотные аккорды, слабые случайные ноты и неестественные раскладки. На выходе получается новый .mid, который легче открыть в секвенсоре и использовать в аранжировке.
        </p>
      </div>

      <div class="section">
        <h2 data-i18n="info.processTitle">Как проходит обработка</h2>
        <div class="steps">
          <div class="mini-card">
            <strong data-i18n="info.step1Title">1. Разбор файла</strong>
            <span data-i18n="info.step1Copy">Сервис читает MIDI-заголовок, tracks, tempo, time signature и события note on/off.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.step2Title">2. Музыкальный анализ</strong>
            <span data-i18n="info.step2Copy">Определяется примерный тональный центр, сетка квантования и плотность фактуры.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.step3Title">3. Исправление нот</strong>
            <span data-i18n="info.step3Copy">Ноты чистятся, приводятся к гамме, выравниваются по сетке и получают новую динамику.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.step4Title">4. Экспорт</strong>
            <span data-i18n="info.step4Copy">Готовый MIDI собирается заново в формате, совместимом с популярными секвенсорами.</span>
          </div>
        </div>
      </div>

      <div class="section">
        <h2 data-i18n="info.fixTitle">Что именно исправляется</h2>
        <div class="features">
          <div class="mini-card">
            <strong data-i18n="info.timingTitle">Тайминг</strong>
            <span data-i18n="info.timingCopy">Ноты аккуратно привязываются к музыкальной сетке без полного уничтожения рисунка партии.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.harmonyTitle">Гармония</strong>
            <span data-i18n="info.harmonyCopy">Ноты вне найденной тональности сдвигаются к ближайшим музыкально логичным ступеням.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.voiceTitle">Голосоведение</strong>
            <span data-i18n="info.voiceCopy">Бас, внутренние голоса и верхняя линия раскладываются по более естественным диапазонам.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.densityTitle">Плотность</strong>
            <span data-i18n="info.densityCopy">Слишком тяжелые кластеры упрощаются, чтобы партия звучала чище и читалась в миксе.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.velocityTitle">Velocity</strong>
            <span data-i18n="info.velocityCopy">Динамика перестраивается с учетом сильных долей, баса и ведущей мелодии.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="info.compatTitle">Совместимость</strong>
            <span data-i18n="info.compatCopy">По умолчанию используется совместимый формат 1, а для простых случаев доступен формат 0.</span>
          </div>
        </div>
      </div>

      <div class="section">
        <h2 data-i18n="info.stylesTitle">Стили обработки</h2>
        <div class="styles">
          <div class="mini-card">
            <strong data-i18n="styleCard.balancedTitle">Сбалансированный</strong>
            <span data-i18n="styleCard.balancedCopy">Универсальная чистка с умеренной плотностью и стабильной верхней линией.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="styleCard.pianoTitle">Фортепиано</strong>
            <span data-i18n="styleCard.pianoCopy">Более фортепианная раскладка с широкими руками и певучим верхним голосом.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="styleCard.classicalTitle">Классика</strong>
            <span data-i18n="styleCard.classicalCopy">Строже относится к четырёхголосию, скачкам и параллельным интервалам.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="styleCard.jazzTitle">Джаз</strong>
            <span data-i18n="styleCard.jazzCopy">Сохраняет больше красок септаккордов, нонаккордов и облегчённых басовых расположений там, где это уместно.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="styleCard.popTitle">Поп</strong>
            <span data-i18n="styleCard.popCopy">Делает партии проще, чище и дружелюбнее к хукам, вокалу и плотному продакшену.</span>
          </div>
          <div class="mini-card">
            <strong data-i18n="styleCard.readyTitle">Готово для секвенсора</strong>
            <span data-i18n="styleCard.readyCopy">После обработки файл сразу скачивается и может быть импортирован в секвенсор.</span>
          </div>
        </div>
      </div>

      <div class="section">
        <h2 data-i18n="limits.title">Ограничения первой версии и что дальше</h2>
        <p data-i18n="limits.copy">
          После обработки браузер скачивает новый MIDI-файл, а на странице появляется короткая статистика: стиль, найденный тональный центр, сетка квантования, количество нот, диапазон и средняя длительность. Но важно понимать, что это пока первый музыкальный слой, а не финальная универсальная система для всех типов партий.
        </p>
        <ul class="result-list">
          <li data-i18n="limits.item1">Лучше всего подходят гармонические, клавишные, аккордовые, струнные, пэдовые и мелодические MIDI-партии.</li>
          <li data-i18n="limits.item2">Барабанные MIDI пока лучше не обрабатывать этим режимом: для них нужен отдельный режим барабанов.</li>
          <li data-i18n="limits.item3">Это первая версия: сервис уже чинит структуру, но позже появятся режимы для баса, мелодии, струнных и обработки по референсу.</li>
        </ul>
      </div>
    </section>
    </section>

    <section class="panel" id="audioPanel">
      <section class="grid">
        <div class="card">
          <div class="pill" data-i18n="audio.pill">Загрузить дорожки · получить мастер WAV</div>
          <label class="dropzone" id="audioDropzone" for="audioInput">
            <input id="audioInput" type="file" accept=".wav,audio/wav,audio/x-wav" multiple>
            <div>
              <div class="drop-title" id="audioFileTitle" data-i18n="audio.dropTitle">Перетащите WAV-дорожки сюда</div>
              <p class="drop-copy" id="audioFileCopy" data-i18n="audio.dropCopy">Загрузите дорожки: барабаны, бас, вокал, гитара, синтезатор или эффекты. Чем понятнее имена файлов, тем лучше агент распознает роли.</p>
            </div>
          </label>
          <div class="file-list" id="audioFileList"></div>
        </div>

        <div class="card">
          <div class="controls">
            <label>
              <span data-i18n="audio.genreLabel">Жанр / характер микса</span>
              <select id="audioGenre">
                <option value="balanced" data-i18n="genre.balanced">Сбалансированный</option>
                <option value="pop" data-i18n="genre.pop">Поп</option>
                <option value="rap" data-i18n="genre.rap">Рэп</option>
                <option value="rock" data-i18n="genre.rock">Рок</option>
                <option value="edm" data-i18n="genre.edm">Электронная музыка</option>
                <option value="cinematic" data-i18n="genre.cinematic">Кино</option>
              </select>
            </label>

            <label>
              <span data-i18n="audio.targetLabel">Цель мастеринга</span>
              <select id="masterTarget">
                <option value="streaming:-14LUFS:-1dBTP" data-i18n="target.streaming">Стриминг −14 LUFS</option>
                <option value="modern:-10LUFS:-1dBTP" data-i18n="target.modern">Современный громкий −10 LUFS</option>
                <option value="club:-8LUFS:-1dBTP" data-i18n="target.club">Клубный громкий −8 LUFS</option>
              </select>
            </label>

            <button id="audioSubmitButton" type="button" data-i18n="audio.submit">Свести и скачать мастер WAV</button>
            <div class="status" id="audioStatus" data-i18n="audio.statusEmpty">WAV-дорожки ещё не выбраны.</div>
          </div>

          <div class="stats" id="audioStats"></div>
          <div class="preview" id="masterPreview">
            <div class="preview-title">
              <span data-i18n="audio.previewTitle">Сравнение A/B</span>
              <span id="masterPreviewMeta">24-бит WAV</span>
            </div>
            <div class="preview-title">
              <span data-i18n="audio.roughMix">Черновое сведение</span>
              <span data-i18n="audio.beforeMaster">до мастеринга</span>
            </div>
            <audio id="roughAudio" controls preload="metadata"></audio>
            <div class="preview-title">
              <span data-i18n="audio.masterTitle">Мастер</span>
              <span data-i18n="audio.afterMaster">после мастеринга</span>
            </div>
            <audio id="masterAudio" controls preload="metadata"></audio>
            <div class="preview-actions">
              <button class="secondary-button" id="downloadMasterButton" type="button" data-i18n="audio.downloadMaster">Скачать мастер WAV</button>
              <button class="secondary-button" id="downloadMixPlanButton" type="button" data-i18n="audio.downloadPlan">Скачать план сведения</button>
              <button class="secondary-button" id="downloadAnalysisButton" type="button" data-i18n="audio.downloadAnalysis">Скачать анализ</button>
            </div>
          </div>
          <p class="hint" data-i18n="audio.hint">
            Сейчас аудио-режим принимает WAV-дорожки и делает быстрый мастер. Лучшие имена файлов: kick.wav, drums.wav, bass.wav, lead_vocal.wav, guitar.wav, synth.wav.
          </p>
        </div>
      </section>

      <section class="info" aria-label="Описание audio mix and master">
        <div class="section">
          <h2 data-i18n="audioInfo.title">Как работает сведение и мастеринг</h2>
          <p data-i18n="audioInfo.copy">
            Сервис сохраняет загруженные WAV-дорожки во временный проект, определяет роль каждой дорожки по имени, анализирует уровень и формат, применяет обработку с учётом роли, суммирует дорожки в стерео-микс и экспортирует готовый 24-битный мастер WAV.
          </p>
          <div class="steps">
            <div class="mini-card">
              <strong data-i18n="audioInfo.step1Title">1. Загрузка дорожек</strong>
              <span data-i18n="audioInfo.step1Copy">Можно отправить несколько WAV-файлов: барабаны, бас, вокал, гитара, синтезатор, эффекты.</span>
            </div>
            <div class="mini-card">
              <strong data-i18n="audioInfo.step2Title">2. Анализ</strong>
              <span data-i18n="audioInfo.step2Copy">Проверяются частота дискретизации, разрядность, пик, средний уровень, клиппинг и длительность.</span>
            </div>
            <div class="mini-card">
              <strong data-i18n="audioInfo.step3Title">3. Звуковая обработка</strong>
              <span data-i18n="audioInfo.step3Copy">Используются выравнивание уровней, фильтры, компрессия, пространство, панорама и ограничение пиков.</span>
            </div>
            <div class="mini-card">
              <strong data-i18n="audioInfo.step4Title">4. Экспорт мастера</strong>
              <span data-i18n="audioInfo.step4Copy">Браузер скачивает мастер WAV, а на странице показывается короткая статистика проекта.</span>
            </div>
          </div>
        </div>

        <div class="section">
          <h2 data-i18n="audioInfo.goodTitle">Что важно для хорошего результата</h2>
          <ul class="result-list">
            <li data-i18n="audioInfo.good1">Загружайте дорожки одной длины и с одинаковой точкой старта, как при экспорте из секвенсора.</li>
            <li data-i18n="audioInfo.good2">Используйте понятные имена файлов: роль дорожки сейчас определяется по имени.</li>
            <li data-i18n="audioInfo.good3">Не загружайте уже сильно клиппующие файлы: мастеринг не сможет вернуть потерянные пики.</li>
            <li data-i18n="audioInfo.good4">Это первая версия рендера: он делает рабочий первый мастер, но позже появятся жанровые пресеты и сравнение до/после.</li>
          </ul>
        </div>
      </section>
    </section>

    <section class="panel" id="pricingPanel">
      <section class="pricing-intro" aria-label="Обзор тарифов">
        <div>
          <div class="pill" data-i18n="pricing.pill">Тарифы для запуска</div>
          <h2 data-i18n="pricing.title">Начните бесплатно. Платите, когда сервис экономит реальное время.</h2>
          <p data-i18n="pricing.copy">
            Используйте iMixing как быстрый редактор MIDI бесплатно. Переходите на платный тариф, когда нужны длинные аудио-рендеры, пакетная обработка, история проектов и приоритетная очередь.
          </p>
        </div>
        <div class="pricing-note">
          <strong data-i18n="pricing.noteTitle">Оплата для России</strong>
          <span data-i18n="pricing.noteCopy">Для российской версии логичны ЮKassa, СБП, карты Мир, карты российских банков и счёт для юридических лиц. Демо-баллы на этой странице пока только имитируют оплату.</span>
        </div>
      </section>

      <section class="pricing-grid" aria-label="Тарифные планы">
        <div class="price-card">
          <div class="price-kicker">
            <div class="pill" data-i18n="plan.freeBadge">Старт</div>
            <span data-i18n="plan.freeMeta">Для первых экспортов</span>
          </div>
          <h2 data-i18n="plan.freeName">Бесплатный</h2>
          <p class="price-copy" data-i18n="plan.freeCopy">Почините черновые MIDI-партии и протестируйте одно короткое аудио-сведение без карты.</p>
          <div class="price" data-i18n="plan.freePrice">0 ₽</div>
          <div class="price-meta" data-i18n="plan.freePriceMeta">Карта не нужна</div>
          <ul>
            <li data-i18n="plan.freeItem1">15 MIDI-экспортов в месяц</li>
            <li data-i18n="plan.freeItem2">1 демо-сведение до 90 секунд</li>
            <li data-i18n="plan.freeItem3">Стили: сбалансированный, фортепиано и поп</li>
            <li data-i18n="plan.freeItem4">Обычная очередь, без истории проектов</li>
          </ul>
          <button class="secondary-button reset-credits" type="button" data-i18n="plan.freeButton">Сбросить демо-баллы</button>
        </div>

        <div class="price-card featured">
          <div class="price-kicker">
            <div class="pill" data-i18n="plan.creatorBadge">Популярный</div>
            <span data-i18n="plan.creatorMeta">Для авторов и продюсеров</span>
          </div>
          <h2 data-i18n="plan.creatorName">Автор</h2>
          <p class="price-copy" data-i18n="plan.creatorCopy">Тариф для регулярной чистки MIDI, вариантов аранжировки и сведения полных дорожек.</p>
          <div class="price" data-i18n="plan.creatorPrice">990 ₽/мес</div>
          <div class="price-meta" data-i18n="plan.creatorPriceMeta">или 9 490 ₽/год</div>
          <ul>
            <li data-i18n="plan.creatorItem1">300 MIDI-экспортов в месяц</li>
            <li data-i18n="plan.creatorItem2">30 аудио-минут в месяц, до 12 дорожек</li>
            <li data-i18n="plan.creatorItem3">Пакетная обработка до 10 MIDI-файлов и сравнение A/B</li>
            <li data-i18n="plan.creatorItem4">История 30 дней, скачивание чернового сведения и мастера</li>
          </ul>
          <button class="credit-pack" type="button" data-credits="80" data-i18n="plan.creatorButton">Загрузить демо тарифа Автор</button>
        </div>

        <div class="price-card">
          <div class="price-kicker">
            <div class="pill" data-i18n="plan.proBadge">Для релизов</div>
            <span data-i18n="plan.proMeta">Для плотной работы</span>
          </div>
          <h2 data-i18n="plan.proName">Профи</h2>
          <p class="price-copy" data-i18n="plan.proCopy">Для активного графика релизов, больших сессий, быстрой очереди и будущих продвинутых режимов.</p>
          <div class="price" data-i18n="plan.proPrice">2 490 ₽/мес</div>
          <div class="price-meta" data-i18n="plan.proPriceMeta">или 23 900 ₽/год</div>
          <ul>
            <li data-i18n="plan.proItem1">MIDI без жёсткого лимита при честном использовании</li>
            <li data-i18n="plan.proItem2">180 аудио-минут в месяц, до 24 дорожек</li>
            <li data-i18n="plan.proItem3">Приоритетная очередь и сравнение версий</li>
            <li data-i18n="plan.proItem4">Ранний доступ к режимам баса, струнных и обработки по референсу</li>
          </ul>
          <button class="secondary-button credit-pack" type="button" data-credits="240" data-i18n="plan.proButton">Загрузить демо тарифа Профи</button>
        </div>

        <div class="price-card">
          <div class="price-kicker">
            <div class="pill" data-i18n="plan.studioBadge">Команды</div>
            <span data-i18n="plan.studioMeta">Клиенты и студии</span>
          </div>
          <h2 data-i18n="plan.studioName">Студия</h2>
          <p class="price-copy" data-i18n="plan.studioCopy">Общий лимит для команд, которым нужны места участников, большой пул рендеров и удобная передача проектов.</p>
          <div class="price" data-i18n="plan.studioPrice">6 900 ₽/мес</div>
          <div class="price-meta" data-i18n="plan.studioPriceMeta">или 66 000 ₽/год</div>
          <ul>
            <li data-i18n="plan.studioItem1">3 участника и общая библиотека проектов</li>
            <li data-i18n="plan.studioItem2">600 аудио-минут в месяц, до 40 дорожек</li>
            <li data-i18n="plan.studioItem3">Самая быстрая очередь, увеличенные лимиты файлов, командная оплата</li>
            <li data-i18n="plan.studioItem4">Подходит для небольших студий, дуэтов и подготовки релизов</li>
          </ul>
          <button class="secondary-button credit-pack" type="button" data-credits="720" data-i18n="plan.studioButton">Загрузить демо тарифа Студия</button>
        </div>
      </section>

      <section class="credit-panel">
        <div class="pricing-detail-grid">
          <div>
            <h2 data-i18n="topups.title">Дополнительные аудио-минуты</h2>
            <p class="hint" data-i18n="topups.copy">
              Для пользователей, которым не нужен тариф выше, но в загруженный месяц требуется больше времени на рендер. Пакеты лучше всего сочетаются с тарифами Автор и Профи.
            </p>
            <div class="topup-grid" aria-label="Пакеты аудио-минут">
              <div class="topup-card">
                <strong data-i18n="topups.smallName">Пакет S</strong>
                <div class="topup-price" data-i18n="topups.smallPrice">790 ₽</div>
                <div class="topup-copy" data-i18n="topups.smallCopy">30 аудио-минут, действуют 12 месяцев.</div>
              </div>
              <div class="topup-card">
                <strong data-i18n="topups.mediumName">Пакет M</strong>
                <div class="topup-price" data-i18n="topups.mediumPrice">1 990 ₽</div>
                <div class="topup-copy" data-i18n="topups.mediumCopy">90 аудио-минут для плотных релизных недель.</div>
              </div>
              <div class="topup-card">
                <strong data-i18n="topups.largeName">Пакет L</strong>
                <div class="topup-price" data-i18n="topups.largePrice">4 990 ₽</div>
                <div class="topup-copy" data-i18n="topups.largeCopy">240 аудио-минут для студий и пакетной сдачи проектов.</div>
              </div>
            </div>
          </div>

          <div>
            <h2 data-i18n="billing.title">Как работает оплата</h2>
            <ul class="result-list">
              <li data-i18n="billing.item1">Редактор MIDI остаётся бесплатным или недорогим, чтобы пользователь мог быстро попробовать сервис.</li>
              <li data-i18n="billing.item2">Платная ценность строится вокруг аудио-минут, пакетных экспортов, истории проектов и приоритетной очереди.</li>
              <li data-i18n="billing.item3">Будущие режимы барабанов, баса, струнных и обработки по референсу сначала входят в платные тарифы.</li>
            </ul>
          </div>
        </div>

        <div class="pricing-demo">
          <div>
            <h2 data-i18n="demo.title">Демо-режим в локальной сборке</h2>
            <p class="hint" data-i18n="demo.copy">
              Платёжный провайдер пока не подключён, поэтому в этой сборке тарифы имитируются через демо-баллы, которые живут только в браузере.
            </p>
            <ul class="result-list">
              <li data-i18n="demo.item1">1 экспорт MIDI списывает 1 демо-балл.</li>
              <li data-i18n="demo.item2">1 задача сведения и мастеринга списывает 5 демо-баллов.</li>
              <li data-i18n="demo.item3">Кнопки ниже просто пополняют локальный баланс для проверки платного доступа и тарифной логики.</li>
            </ul>
          </div>
          <div class="credit-actions">
            <button class="credit-pack" type="button" data-credits="15" data-i18n="demo.add15">Добавить 15 демо-баллов</button>
            <button class="credit-pack" type="button" data-credits="60" data-i18n="demo.add60">Добавить 60 демо-баллов</button>
            <button class="credit-pack" type="button" data-credits="180" data-i18n="demo.add180">Добавить 180 демо-баллов</button>
            <button class="secondary-button reset-credits" type="button" data-i18n="demo.reset">Сбросить до бесплатного демо</button>
          </div>
        </div>
      </section>
    </section>
  </main>

  <script>
    const fileInput = document.getElementById("fileInput");
    const dropzone = document.getElementById("dropzone");
    const submitButton = document.getElementById("submitButton");
    const statusEl = document.getElementById("status");
    const statsEl = document.getElementById("stats");
    const fileTitle = document.getElementById("fileTitle");
    const fileCopy = document.getElementById("fileCopy");
    const creditBalanceEl = document.getElementById("creditBalance");
    const creditPackButtons = document.querySelectorAll(".credit-pack[data-credits]");
    const resetCreditsButtons = document.querySelectorAll(".reset-credits");
    const familyButtons = document.querySelectorAll(".family-chip[data-family]");
    const familyCopyEl = document.getElementById("familyCopy");
    const style = document.getElementById("style");
    const outputFormat = document.getElementById("outputFormat");
    const includeTitles = document.getElementById("includeTitles");
    const tabButtons = document.querySelectorAll(".tab-button");
    const panels = document.querySelectorAll(".panel");
    const languageButtons = document.querySelectorAll(".language-button[data-lang]");
    const audioInput = document.getElementById("audioInput");
    const audioDropzone = document.getElementById("audioDropzone");
    const audioSubmitButton = document.getElementById("audioSubmitButton");
    const audioStatusEl = document.getElementById("audioStatus");
    const audioStatsEl = document.getElementById("audioStats");
    const audioFileTitle = document.getElementById("audioFileTitle");
    const audioFileCopy = document.getElementById("audioFileCopy");
    const audioFileList = document.getElementById("audioFileList");
    const audioGenre = document.getElementById("audioGenre");
    const masterTarget = document.getElementById("masterTarget");
    const masterPreview = document.getElementById("masterPreview");
    const masterAudio = document.getElementById("masterAudio");
    const roughAudio = document.getElementById("roughAudio");
    const masterPreviewMeta = document.getElementById("masterPreviewMeta");
    const downloadMasterButton = document.getElementById("downloadMasterButton");
    const downloadMixPlanButton = document.getElementById("downloadMixPlanButton");
    const downloadAnalysisButton = document.getElementById("downloadAnalysisButton");
    const translations = {
      ru: {
        "meta.title": "iMixing — редактор MIDI",
        "hero.eyebrow": "iMixing · редактор MIDI",
        "hero.title": "Правим MIDI так, чтобы он звучал собранно.",
        "hero.subtitle": "Загрузите MIDI для музыкального исправления или WAV-дорожки для быстрого сведения и мастеринга. Сервис обработает материал и отдаст готовый файл обратно.",
        "credits.label": "демо-баллы",
        "tabs.midi": "Редактор MIDI",
        "tabs.midiMeta": "правка · гармония · экспорт",
        "tabs.audio": "Сведение и мастеринг",
        "tabs.audioMeta": "дорожки · LUFS · мастер WAV",
        "tabs.pricing": "Тарифы",
        "tabs.pricingMeta": "баллы · планы · лимиты",
        "midi.pill": "Перетащить · исправить · скачать",
        "midi.drumsLabel": "Барабаны позже",
        "midi.drumsTitle": "Барабанные MIDI пока лучше не загружать в этот режим.",
        "midi.drumsCopy": "Для барабанных партий нужен отдельный режим с другой логикой грува, силы ударов, тихих нот и раскладки по пэдам.",
        "midi.dropTitle": "Перетащите `.mid` сюда",
        "midi.dropCopy": "Или нажмите, чтобы выбрать файл. Лучше всего подходят обычные MIDI-партии из нотного редактора без редких служебных событий.",
        "midi.familyTitle": "Тип партии",
        "midi.styleLabel": "Музыкальный стиль",
        "midi.formatLabel": "Формат вывода",
        "midi.includeTitles": "Добавлять названия треков в MIDI",
        "midi.submit": "Исправить и скачать",
        "midi.statusEmpty": "Файл ещё не выбран.",
        "midi.ready": "Готово к обработке.",
        "midi.processing": "Исправляю MIDI...",
        "midi.pickFirst": "Сначала выберите MIDI-файл.",
        "midi.done": "Готово. Скачан файл {filename}. Списан 1 демо-балл.",
        "midi.hint": "Для большинства секвенсоров лучше оставить совместимый формат 1. Если программа всё равно открывает файл некорректно, попробуйте простой MIDI, формат 0. Для фортепианных партий обычно лучше стиль «Фортепиано», для плотных аккордов — «Джаз». Барабанные MIDI пока лучше не загружать: для них нужен отдельный режим.",
        "family.harmony": "Гармония",
        "family.keys": "Клавиши",
        "family.melody": "Мелодия",
        "family.drumsSoon": "Барабаны · скоро",
        "family.harmonyHint": "Гармония подходит для аккордов, пэдов, многоголосных партий и общих гармонических MIDI-фрагментов.",
        "family.keysHint": "Клавиши лучше использовать для фортепианных и клавишных партий, где важна раскладка рук.",
        "family.melodyHint": "Мелодия лучше подходит для лидов, верхних линий и линейных одноголосных фраз.",
        "audio.pill": "Загрузить дорожки · получить мастер WAV",
        "audio.dropTitle": "Перетащите WAV-дорожки сюда",
        "audio.dropCopy": "Загрузите дорожки: барабаны, бас, вокал, гитара, синтезатор или эффекты. Чем понятнее имена файлов, тем лучше агент распознает роли.",
        "audio.genreLabel": "Жанр / характер микса",
        "audio.targetLabel": "Цель мастеринга",
        "audio.submit": "Свести и скачать мастер WAV",
        "audio.statusEmpty": "WAV-дорожки ещё не выбраны.",
        "audio.ready": "Готово к сведению.",
        "audio.pickFirst": "Сначала выберите WAV-дорожки.",
        "audio.processing": "Свожу дорожки и мастерю WAV...",
        "audio.queued": "Задача поставлена в очередь...",
        "audio.running": "Рендерю дорожки, собираю черновое сведение и мастер...",
        "audio.created": "Задача создана: {id}",
        "audio.done": "Готово. Списано 5 демо-баллов. Можно сравнить черновое сведение и мастер.",
        "audio.previewTitle": "Сравнение до/после",
        "audio.roughMix": "Черновое сведение",
        "audio.beforeMaster": "до мастеринга",
        "audio.afterMaster": "после мастеринга",
        "audio.masterTitle": "Мастер",
        "audio.downloadMaster": "Скачать мастер WAV",
        "audio.downloadPlan": "Скачать план сведения",
        "audio.downloadAnalysis": "Скачать анализ",
        "audio.hint": "Сейчас аудио-режим принимает WAV-дорожки и делает быстрый мастер. Лучшие имена файлов: kick.wav, drums.wav, bass.wav, lead_vocal.wav, guitar.wav, synth.wav.",
        "credits.insufficient": "{feature} требует {cost} демо-баллов. Откройте тарифы и пополните демо-баланс.",
        "feature.midi": "Редактор MIDI",
        "feature.audio": "Сведение и мастеринг",
        "pricing.pill": "Тарифы для запуска",
        "pricing.title": "Начните бесплатно. Платите, когда сервис экономит реальное время.",
        "pricing.copy": "Используйте iMixing как быстрый редактор MIDI бесплатно. Переходите на платный тариф, когда нужны длинные аудио-рендеры, пакетная обработка, история проектов и приоритетная очередь.",
        "pricing.noteTitle": "Оплата для России",
        "pricing.noteCopy": "Для российской версии логичны ЮKassa, СБП, карты Мир, карты российских банков и счёт для юридических лиц. Демо-баллы на этой странице пока только имитируют оплату.",
        "info.whatTitle": "Что делает сервис",
        "info.whatCopy": "Редактор MIDI принимает файл, разбирает ноты и музыкальную структуру, исправляет неаккуратный тайминг, слишком плотные аккорды, слабые случайные ноты и неестественные раскладки. На выходе получается новый .mid, который легче открыть в секвенсоре и использовать в аранжировке.",
        "info.processTitle": "Как проходит обработка",
        "info.step1Title": "1. Разбор файла",
        "info.step1Copy": "Сервис читает MIDI-заголовок, tracks, tempo, time signature и события note on/off.",
        "info.step2Title": "2. Музыкальный анализ",
        "info.step2Copy": "Определяется примерный тональный центр, сетка квантования и плотность фактуры.",
        "info.step3Title": "3. Исправление нот",
        "info.step3Copy": "Ноты чистятся, приводятся к гамме, выравниваются по сетке и получают новую динамику.",
        "info.step4Title": "4. Экспорт",
        "info.step4Copy": "Готовый MIDI собирается заново в формате, совместимом с популярными секвенсорами.",
        "info.fixTitle": "Что именно исправляется",
        "info.timingTitle": "Тайминг",
        "info.timingCopy": "Ноты аккуратно привязываются к музыкальной сетке без полного уничтожения рисунка партии.",
        "info.harmonyTitle": "Гармония",
        "info.harmonyCopy": "Ноты вне найденной тональности сдвигаются к ближайшим музыкально логичным ступеням.",
        "info.voiceTitle": "Голосоведение",
        "info.voiceCopy": "Бас, внутренние голоса и верхняя линия раскладываются по более естественным диапазонам.",
        "info.densityTitle": "Плотность",
        "info.densityCopy": "Слишком тяжелые кластеры упрощаются, чтобы партия звучала чище и читалась в миксе.",
        "info.velocityTitle": "Сила нот",
        "info.velocityCopy": "Динамика перестраивается с учетом сильных долей, баса и ведущей мелодии.",
        "info.compatTitle": "Совместимость",
        "info.compatCopy": "По умолчанию используется совместимый формат 1, а для простых случаев доступен формат 0.",
        "info.stylesTitle": "Стили обработки",
        "style.balanced": "Сбалансированный",
        "style.piano": "Фортепиано",
        "style.classical": "Классика",
        "style.jazz": "Джаз",
        "style.pop": "Поп",
        "format.ableton": "Совместимый формат 1",
        "format.plain": "Простой MIDI, формат 0",
        "genre.balanced": "Сбалансированный",
        "genre.pop": "Поп",
        "genre.rap": "Рэп",
        "genre.rock": "Рок",
        "genre.edm": "Электронная музыка",
        "genre.cinematic": "Кино",
        "target.streaming": "Стриминг −14 LUFS",
        "target.modern": "Современный громкий −10 LUFS",
        "target.club": "Клубный громкий −8 LUFS",
        "styleCard.balancedTitle": "Сбалансированный",
        "styleCard.balancedCopy": "Универсальная чистка с умеренной плотностью и стабильной верхней линией.",
        "styleCard.pianoTitle": "Фортепиано",
        "styleCard.pianoCopy": "Более фортепианная раскладка с широкими руками и певучим верхним голосом.",
        "styleCard.classicalTitle": "Классика",
        "styleCard.classicalCopy": "Строже относится к четырёхголосию, скачкам и параллельным интервалам.",
        "styleCard.jazzTitle": "Джаз",
        "styleCard.jazzCopy": "Сохраняет больше красок септаккордов, нонаккордов и облегчённых басовых расположений там, где это уместно.",
        "styleCard.popTitle": "Поп",
        "styleCard.popCopy": "Делает партии проще, чище и дружелюбнее к хукам, вокалу и плотному продакшену.",
        "styleCard.readyTitle": "Готово для секвенсора",
        "styleCard.readyCopy": "После обработки файл сразу скачивается и может быть импортирован в секвенсор.",
        "limits.title": "Ограничения первой версии и что дальше",
        "limits.copy": "После обработки браузер скачивает новый MIDI-файл, а на странице появляется короткая статистика: стиль, найденный тональный центр, сетка квантования, количество нот, диапазон и средняя длительность. Но важно понимать, что это пока первый музыкальный слой, а не финальная универсальная система для всех типов партий.",
        "limits.item1": "Лучше всего подходят гармонические, клавишные, аккордовые, струнные, пэдовые и мелодические MIDI-партии.",
        "limits.item2": "Барабанные MIDI пока лучше не обрабатывать этим режимом: для них нужен отдельный режим барабанов.",
        "limits.item3": "Это первая версия: сервис уже чинит структуру, но позже появятся режимы для баса, мелодии, струнных и обработки по референсу.",
        "audioInfo.title": "Как работает сведение и мастеринг",
        "audioInfo.copy": "Сервис сохраняет загруженные WAV-дорожки во временный проект, определяет роль каждой дорожки по имени, анализирует уровень и формат, применяет обработку с учётом роли, суммирует дорожки в стерео-микс и экспортирует готовый 24-битный мастер WAV.",
        "audioInfo.step1Title": "1. Загрузка дорожек",
        "audioInfo.step1Copy": "Можно отправить несколько WAV-файлов: барабаны, бас, вокал, гитара, синтезатор, эффекты.",
        "audioInfo.step2Title": "2. Анализ",
        "audioInfo.step2Copy": "Проверяются частота дискретизации, разрядность, пик, средний уровень, клиппинг и длительность.",
        "audioInfo.step3Title": "3. Звуковая обработка",
        "audioInfo.step3Copy": "Используются выравнивание уровней, фильтры, компрессия, пространство, панорама и ограничение пиков.",
        "audioInfo.step4Title": "4. Экспорт мастера",
        "audioInfo.step4Copy": "Браузер скачивает мастер WAV, а на странице показывается короткая статистика проекта.",
        "audioInfo.goodTitle": "Что важно для хорошего результата",
        "audioInfo.good1": "Загружайте дорожки одной длины и с одинаковой точкой старта, как при экспорте из секвенсора.",
        "audioInfo.good2": "Используйте понятные имена файлов: роль дорожки сейчас определяется по имени.",
        "audioInfo.good3": "Не загружайте уже сильно клиппующие файлы: мастеринг не сможет вернуть потерянные пики.",
        "audioInfo.good4": "Это первая версия рендера: он делает рабочий первый мастер, но позже появятся жанровые пресеты и сравнение до/после.",
        "plan.freeBadge": "Старт",
        "plan.freeMeta": "Для первых экспортов",
        "plan.freeName": "Бесплатный",
        "plan.freeCopy": "Почините черновые MIDI-партии и протестируйте одно короткое аудио-сведение без карты.",
        "plan.freePrice": "0 ₽",
        "plan.freePriceMeta": "Карта не нужна",
        "plan.freeItem1": "15 MIDI-экспортов в месяц",
        "plan.freeItem2": "1 демо-сведение до 90 секунд",
        "plan.freeItem3": "Стили: сбалансированный, фортепиано и поп",
        "plan.freeItem4": "Обычная очередь, без истории проектов",
        "plan.freeButton": "Сбросить демо-баллы",
        "plan.creatorBadge": "Популярный",
        "plan.creatorMeta": "Для авторов и продюсеров",
        "plan.creatorName": "Автор",
        "plan.creatorCopy": "Тариф для регулярной чистки MIDI, вариантов аранжировки и сведения полных дорожек.",
        "plan.creatorPrice": "990 ₽/мес",
        "plan.creatorPriceMeta": "или 9 490 ₽/год",
        "plan.creatorItem1": "300 MIDI-экспортов в месяц",
        "plan.creatorItem2": "30 аудио-минут в месяц, до 12 дорожек",
        "plan.creatorItem3": "Пакетная обработка до 10 MIDI-файлов и сравнение A/B",
        "plan.creatorItem4": "История 30 дней, скачивание чернового сведения и мастера",
        "plan.creatorButton": "Загрузить демо тарифа Автор",
        "plan.proBadge": "Для релизов",
        "plan.proMeta": "Для плотной работы",
        "plan.proName": "Профи",
        "plan.proCopy": "Для активного графика релизов, больших сессий, быстрой очереди и будущих продвинутых режимов.",
        "plan.proPrice": "2 490 ₽/мес",
        "plan.proPriceMeta": "или 23 900 ₽/год",
        "plan.proItem1": "MIDI без жёсткого лимита при честном использовании",
        "plan.proItem2": "180 аудио-минут в месяц, до 24 дорожек",
        "plan.proItem3": "Приоритетная очередь и сравнение версий",
        "plan.proItem4": "Ранний доступ к режимам баса, струнных и обработки по референсу",
        "plan.proButton": "Загрузить демо тарифа Профи",
        "plan.studioBadge": "Команды",
        "plan.studioMeta": "Клиенты и студии",
        "plan.studioName": "Студия",
        "plan.studioCopy": "Общий лимит для команд, которым нужны места участников, большой пул рендеров и удобная передача проектов.",
        "plan.studioPrice": "6 900 ₽/мес",
        "plan.studioPriceMeta": "или 66 000 ₽/год",
        "plan.studioItem1": "3 участника и общая библиотека проектов",
        "plan.studioItem2": "600 аудио-минут в месяц, до 40 дорожек",
        "plan.studioItem3": "Самая быстрая очередь, увеличенные лимиты файлов, командная оплата",
        "plan.studioItem4": "Подходит для небольших студий, дуэтов и подготовки релизов",
        "plan.studioButton": "Загрузить демо тарифа Студия",
        "topups.title": "Дополнительные аудио-минуты",
        "topups.copy": "Для пользователей, которым не нужен тариф выше, но в загруженный месяц требуется больше времени на рендер. Пакеты лучше всего сочетаются с тарифами Автор и Профи.",
        "topups.smallName": "Пакет S",
        "topups.smallPrice": "790 ₽",
        "topups.smallCopy": "30 аудио-минут, действуют 12 месяцев.",
        "topups.mediumName": "Пакет M",
        "topups.mediumPrice": "1 990 ₽",
        "topups.mediumCopy": "90 аудио-минут для плотных релизных недель.",
        "topups.largeName": "Пакет L",
        "topups.largePrice": "4 990 ₽",
        "topups.largeCopy": "240 аудио-минут для студий и пакетной сдачи проектов.",
        "billing.title": "Как работает оплата",
        "billing.item1": "Редактор MIDI остаётся бесплатным или недорогим, чтобы пользователь мог быстро попробовать сервис.",
        "billing.item2": "Платная ценность строится вокруг аудио-минут, пакетных экспортов, истории проектов и приоритетной очереди.",
        "billing.item3": "Будущие режимы барабанов, баса, струнных и обработки по референсу сначала входят в платные тарифы.",
        "demo.title": "Демо-режим в локальной сборке",
        "demo.copy": "Платёжный провайдер пока не подключён, поэтому в этой сборке тарифы имитируются через демо-баллы, которые живут только в браузере.",
        "demo.item1": "1 экспорт MIDI списывает 1 демо-балл.",
        "demo.item2": "1 задача сведения и мастеринга списывает 5 демо-баллов.",
        "demo.item3": "Кнопки ниже просто пополняют локальный баланс для проверки платного доступа и тарифной логики.",
        "demo.add15": "Добавить 15 демо-баллов",
        "demo.add60": "Добавить 60 демо-баллов",
        "demo.add180": "Добавить 180 демо-баллов",
        "demo.reset": "Сбросить до бесплатного демо"
      },
      en: {
        "meta.title": "iMixing — MIDI repair and mastering",
        "hero.eyebrow": "iMixing MIDI Doctor",
        "hero.title": "Make MIDI feel arranged, not random.",
        "hero.subtitle": "Upload MIDI for musical repair or WAV stems for a fast mix and master. The service analyzes the material, processes it, and returns a clean export.",
        "credits.label": "demo credits",
        "tabs.midi": "MIDI Doctor",
        "tabs.midiMeta": "repair · harmony · export",
        "tabs.audio": "Mix & Master",
        "tabs.audioMeta": "stems · LUFS · master.wav",
        "tabs.pricing": "Pricing",
        "tabs.pricingMeta": "credits · plans · limits",
        "midi.pill": "Drag, drop, repair",
        "midi.drumsLabel": "No Drums Yet",
        "midi.drumsTitle": "Drum MIDI is better kept out of this mode for now.",
        "midi.drumsCopy": "Drum parts need a separate drum doctor with groove, velocity, ghost-note, and pad-mapping logic.",
        "midi.dropTitle": "Drop a `.mid` file here",
        "midi.dropCopy": "Or click to choose a file. Standard piano-roll MIDI works best; avoid exotic SysEx-heavy files.",
        "midi.familyTitle": "Instrument family",
        "midi.styleLabel": "Musical style",
        "midi.formatLabel": "Output format",
        "midi.includeTitles": "Add track names to MIDI",
        "midi.submit": "Repair and download",
        "midi.statusEmpty": "No file selected yet.",
        "midi.ready": "Ready to process.",
        "midi.processing": "Repairing MIDI...",
        "midi.pickFirst": "Choose a MIDI file first.",
        "midi.done": "Done. Downloaded {filename}. Spent 1 demo credit.",
        "midi.hint": "For most DAWs, keep Ableton-safe enabled. If your sequencer still complains, try Plain MIDI. Piano works best for keyboard parts; Jazz keeps denser chord colors. Avoid drum MIDI for now: it needs a separate drum doctor.",
        "family.harmony": "Harmony",
        "family.keys": "Keys",
        "family.melody": "Melody",
        "family.drumsSoon": "Drums · soon",
        "family.harmonyHint": "Harmony is best for chords, pads, chord stacks, and general harmonic MIDI fragments.",
        "family.keysHint": "Keys is better for piano and keyboard voicings where hand layout matters.",
        "family.melodyHint": "Melody is best for leads, toplines, and linear single-note phrases.",
        "audio.pill": "Upload stems, get master.wav",
        "audio.dropTitle": "Drop WAV stems here",
        "audio.dropCopy": "Upload stems: drums, bass, vocal, guitar, synth, or fx. Clear filenames help the agent detect roles.",
        "audio.genreLabel": "Mix genre / character",
        "audio.targetLabel": "Mastering target",
        "audio.submit": "Mix and download master.wav",
        "audio.statusEmpty": "No WAV stems selected yet.",
        "audio.ready": "Ready to mix.",
        "audio.pickFirst": "Choose WAV stems first.",
        "audio.processing": "Mixing stems and mastering WAV...",
        "audio.queued": "Job is queued...",
        "audio.running": "Rendering stems, rough mix, and master...",
        "audio.created": "Job created: {id}",
        "audio.done": "Done. Spent 5 demo credits. You can compare rough mix and master.",
        "audio.previewTitle": "A/B preview",
        "audio.roughMix": "Rough mix",
        "audio.beforeMaster": "before mastering",
        "audio.afterMaster": "after mastering",
        "audio.masterTitle": "Master",
        "audio.downloadMaster": "Download master.wav",
        "audio.downloadPlan": "Download mix_plan.md",
        "audio.downloadAnalysis": "Download analysis.json",
        "audio.hint": "The audio flow accepts WAV stems and creates a fast studio-style master. Best filenames: kick.wav, drums.wav, bass.wav, lead_vocal.wav, guitar.wav, synth.wav.",
        "credits.insufficient": "{feature} needs {cost} demo credit(s). Open Pricing and refill the demo balance.",
        "feature.midi": "MIDI fix",
        "feature.audio": "Mix & Master",
        "pricing.pill": "Launch pricing",
        "pricing.title": "Start free. Upgrade when the workflow starts saving real hours.",
        "pricing.copy": "Use iMixing as a fast MIDI doctor for free. Move to Creator or Pro when you need batch processing, advanced repair modes, longer audio renders, and priority delivery.",
        "pricing.noteTitle": "Annual billing saves 20%",
        "pricing.noteCopy": "MIDI stays low-friction for growth. Paid value comes from audio minutes, faster queue, project history, and future doctors for bass, drums, strings, and reference style.",
        "info.whatTitle": "What the service does",
        "info.whatCopy": "iMixing MIDI Doctor reads a MIDI file, analyzes the notes and musical structure, then repairs loose timing, dense chords, weak stray notes, and unnatural voicings. The result is a cleaner .mid that is easier to open in a DAW and use in an arrangement.",
        "info.processTitle": "How processing works",
        "info.step1Title": "1. File parsing",
        "info.step1Copy": "The service reads the MIDI header, tracks, tempo, time signature, and note on/off events.",
        "info.step2Title": "2. Musical analysis",
        "info.step2Copy": "It estimates key center, quantize grid, and arrangement density.",
        "info.step3Title": "3. Note repair",
        "info.step3Copy": "Notes are cleaned, moved toward the scale, aligned to the grid, and given new dynamics.",
        "info.step4Title": "4. Export",
        "info.step4Copy": "The repaired MIDI is rebuilt in a format compatible with popular DAWs.",
        "info.fixTitle": "What gets repaired",
        "info.timingTitle": "Timing",
        "info.timingCopy": "Notes are aligned to the musical grid without erasing the feel of the part.",
        "info.harmonyTitle": "Harmony",
        "info.harmonyCopy": "Out-of-key notes move toward nearby musically logical scale degrees.",
        "info.voiceTitle": "Voice leading",
        "info.voiceCopy": "Bass, inner voices, and top lines are distributed into more natural ranges.",
        "info.densityTitle": "Density",
        "info.densityCopy": "Overloaded clusters are simplified so the part reads cleaner in a mix.",
        "info.velocityTitle": "Velocity",
        "info.velocityCopy": "Dynamics are rebuilt around downbeats, bass movement, and the lead melody.",
        "info.compatTitle": "Compatibility",
        "info.compatCopy": "Ableton-safe format 1 is used by default; format 0 is available for simpler cases.",
        "info.stylesTitle": "Processing styles",
        "style.balanced": "Balanced",
        "style.piano": "Piano",
        "style.classical": "Classical",
        "style.jazz": "Jazz",
        "style.pop": "Pop",
        "format.ableton": "Ableton-safe format 1",
        "format.plain": "Plain MIDI, format 0",
        "genre.balanced": "Balanced",
        "genre.pop": "Pop",
        "genre.rap": "Rap",
        "genre.rock": "Rock",
        "genre.edm": "EDM",
        "genre.cinematic": "Cinematic",
        "target.streaming": "Streaming −14 LUFS",
        "target.modern": "Modern loud −10 LUFS",
        "target.club": "Club loud −8 LUFS",
        "styleCard.balancedTitle": "Balanced",
        "styleCard.balancedCopy": "Universal cleanup with moderate density and a stable top line.",
        "styleCard.pianoTitle": "Piano",
        "styleCard.pianoCopy": "More pianistic spacing with wider hands and a singing upper voice.",
        "styleCard.classicalTitle": "Classical",
        "styleCard.classicalCopy": "Stricter about four-part writing, leaps, and parallel intervals.",
        "styleCard.jazzTitle": "Jazz",
        "styleCard.jazzCopy": "Preserves more sevenths, ninths, and root-light voicings where they make musical sense.",
        "styleCard.popTitle": "Pop",
        "styleCard.popCopy": "Makes parts simpler, cleaner, and friendlier to hooks, vocals, and dense production.",
        "styleCard.readyTitle": "DAW-ready",
        "styleCard.readyCopy": "After processing, the file downloads immediately and can be imported into a sequencer.",
        "limits.title": "MVP limits and what comes next",
        "limits.copy": "After processing, the browser downloads a new MIDI file and the page shows a short report: style, detected key center, quantize grid, note count, range, and average duration. This is the first musical layer, not a universal final system for every kind of part.",
        "limits.item1": "Best suited for harmonic, keyboard, chord, string, pad, and melodic MIDI parts.",
        "limits.item2": "Drum MIDI should not use this mode yet; it needs a dedicated drum mode.",
        "limits.item3": "This is the first version: the service already repairs structure, and later it will add bass, melody, strings, and reference-style modes.",
        "audioInfo.title": "How Mix & Master works",
        "audioInfo.copy": "The service saves uploaded WAV stems into a temporary project, detects each role by filename, analyzes level and format, applies role-aware processing, sums stems into a stereo mix, and exports a 24-bit master WAV.",
        "audioInfo.step1Title": "1. Stem upload",
        "audioInfo.step1Copy": "You can send several WAV files: drums, bass, vocal, guitar, synth, and effects.",
        "audioInfo.step2Title": "2. Analysis",
        "audioInfo.step2Copy": "Sample rate, bit depth, peak, average level, clipping, and duration are checked.",
        "audioInfo.step3Title": "3. Audio processing",
        "audioInfo.step3Copy": "The chain uses gain staging, filters, compression, space, panning, and peak limiting.",
        "audioInfo.step4Title": "4. Master export",
        "audioInfo.step4Copy": "The browser downloads the master WAV and the page shows a short project report.",
        "audioInfo.goodTitle": "What helps the result",
        "audioInfo.good1": "Upload stems with the same length and start point, just like a DAW export.",
        "audioInfo.good2": "Use clear filenames: the current role detection is filename-based.",
        "audioInfo.good3": "Avoid already-clipped files: mastering cannot restore lost peaks.",
        "audioInfo.good4": "This is the first render version: it creates a usable first master, with genre presets and before/after comparison coming later.",
        "plan.freeBadge": "Start",
        "plan.freeMeta": "For first exports",
        "plan.freeName": "Free",
        "plan.freeCopy": "Repair rough MIDI sketches and test one short audio mix without entering a card.",
        "plan.freePrice": "$0",
        "plan.freePriceMeta": "No credit card required",
        "plan.freeItem1": "15 MIDI exports per month",
        "plan.freeItem2": "1 demo audio mix up to 90 seconds",
        "plan.freeItem3": "Balanced, Piano, and Pop styles",
        "plan.freeItem4": "Standard queue, no project history",
        "plan.freeButton": "Reset demo credits",
        "plan.creatorBadge": "Popular",
        "plan.creatorMeta": "For artists and producers",
        "plan.creatorName": "Creator",
        "plan.creatorCopy": "A plan for regular MIDI cleanup, arrangement variations, and full stem mixing.",
        "plan.creatorPrice": "$12/mo",
        "plan.creatorPriceMeta": "or $96/year",
        "plan.creatorItem1": "300 MIDI exports per month",
        "plan.creatorItem2": "30 audio minutes per month, up to 12 stems",
        "plan.creatorItem3": "Batch MIDI up to 10 files and A/B comparison",
        "plan.creatorItem4": "30-day history, rough mix and master downloads",
        "plan.creatorButton": "Load Creator demo",
        "plan.proBadge": "For releases",
        "plan.proMeta": "For heavy use",
        "plan.proName": "Pro",
        "plan.proCopy": "For active release schedules, larger sessions, faster queue, and future advanced modes.",
        "plan.proPrice": "$29/mo",
        "plan.proPriceMeta": "or $228/year",
        "plan.proItem1": "Unlimited MIDI fair use",
        "plan.proItem2": "180 audio minutes per month, up to 24 stems",
        "plan.proItem3": "Priority queue and version comparison",
        "plan.proItem4": "Early access to bass, strings, and reference-style modes",
        "plan.proButton": "Load Pro demo",
        "plan.studioBadge": "Teams",
        "plan.studioMeta": "Clients and studios",
        "plan.studioName": "Studio",
        "plan.studioCopy": "Shared usage for teams that need seats, a larger render pool, and smoother project handoff.",
        "plan.studioPrice": "$79/mo",
        "plan.studioPriceMeta": "or $708/year",
        "plan.studioItem1": "3 seats and shared project library",
        "plan.studioItem2": "600 audio minutes per month, up to 40 stems",
        "plan.studioItem3": "Fastest queue, larger file limits, team billing",
        "plan.studioItem4": "Great for small studios, duos, and release prep",
        "plan.studioButton": "Load Studio demo",
        "topups.title": "Audio top-ups",
        "topups.copy": "For users who do not need a higher plan but need more render time in a busy month. Top-ups pair best with Creator and Pro.",
        "topups.smallName": "Top-Up S",
        "topups.smallPrice": "$9",
        "topups.smallCopy": "30 audio minutes, valid for 12 months.",
        "topups.mediumName": "Top-Up M",
        "topups.mediumPrice": "$24",
        "topups.mediumCopy": "90 audio minutes for heavy release weeks.",
        "topups.largeName": "Top-Up L",
        "topups.largePrice": "$59",
        "topups.largeCopy": "240 audio minutes for studios and batch delivery.",
        "billing.title": "How billing works",
        "billing.item1": "MIDI repair stays free or low-cost so users can try the service quickly.",
        "billing.item2": "Paid value comes from audio minutes, batch exports, project history, and priority queue.",
        "billing.item3": "Future drum, bass, strings, and reference-style modes enter paid plans first.",
        "demo.title": "Demo mode in this local build",
        "demo.copy": "No payment provider is connected yet, so this build simulates plans with demo credits stored in the browser.",
        "demo.item1": "1 MIDI export spends 1 demo credit.",
        "demo.item2": "1 Mix & Master job spends 5 demo credits.",
        "demo.item3": "The buttons below only refill the local balance for paywall and pricing UX checks.",
        "demo.add15": "Add 15 demo credits",
        "demo.add60": "Add 60 demo credits",
        "demo.add180": "Add 180 demo credits",
        "demo.reset": "Reset to Free demo"
      }
    };
    let currentLanguage = localStorage.getItem("imixing_language") || "ru";
    const familyHints = {
      harmony: "family.harmonyHint",
      keys: "family.keysHint",
      melody: "family.melodyHint",
    };
    const familyStyleDefaults = {
      harmony: "balanced",
      keys: "piano",
      melody: "pop",
    };
    let currentFile = null;
    let currentAudioFiles = [];
    let currentMaster = null;
    let currentFamily = "harmony";
    let styleTouched = false;
    let creditBalance = loadCredits();

    function t(key, replacements = {}) {
      const dictionary = translations[currentLanguage] || translations.ru;
      let value = dictionary[key] || translations.ru[key] || key;
      Object.entries(replacements).forEach(([name, replacement]) => {
        value = value.replaceAll(`{${name}}`, replacement);
      });
      return value;
    }

    function applyLanguage(language) {
      currentLanguage = translations[language] ? language : "ru";
      localStorage.setItem("imixing_language", currentLanguage);
      document.documentElement.lang = currentLanguage;
      document.title = t("meta.title");
      document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.dataset.i18n;
        if (key) {
          element.textContent = t(key);
        }
      });
      languageButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.lang === currentLanguage);
      });
      setFamily(currentFamily);
      if (!currentFile) {
        fileTitle.textContent = t("midi.dropTitle");
        fileCopy.textContent = t("midi.dropCopy");
        statusEl.textContent = t("midi.statusEmpty");
      } else {
        fileTitle.textContent = currentFile.name;
        fileCopy.textContent = `${Math.max(1, Math.round(currentFile.size / 1024))} KB`;
      }
      if (!currentAudioFiles.length) {
        audioFileTitle.textContent = t("audio.dropTitle");
        audioFileCopy.textContent = t("audio.dropCopy");
        audioStatusEl.textContent = t("audio.statusEmpty");
      } else {
        const totalSize = currentAudioFiles.reduce((sum, file) => sum + file.size, 0);
        audioFileTitle.textContent = currentLanguage === "en"
          ? `${currentAudioFiles.length} WAV stem(s) selected`
          : `${currentAudioFiles.length} WAV stem(s) выбрано`;
        audioFileCopy.textContent = `${Math.max(1, Math.round(totalSize / 1024 / 1024))} MB total`;
      }
    }

    function loadCredits() {
      const stored = Number(localStorage.getItem("imixing_mock_credits"));
      if (Number.isFinite(stored) && stored >= 0) {
        return stored;
      }
      localStorage.setItem("imixing_mock_credits", "5");
      return 5;
    }

    function setCredits(nextBalance) {
      creditBalance = Math.max(0, Number(nextBalance) || 0);
      localStorage.setItem("imixing_mock_credits", String(creditBalance));
      creditBalanceEl.textContent = creditBalance;
    }

    async function refreshCredits() {
      try {
        const response = await fetch("/api/credits");
        const payload = await response.json();
        if (response.ok && Number.isFinite(Number(payload.balance))) {
          setCredits(payload.balance);
        }
      } catch (error) {
        console.warn("Credit refresh failed", error);
      }
    }

    async function addCredits(amount) {
      try {
        const response = await fetch("/api/credits/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "Не удалось пополнить demo credits.");
        }
        setCredits(payload.balance);
      } catch (error) {
        setCredits(creditBalance + amount);
      }
    }

    async function resetCredits() {
      try {
        const response = await fetch("/api/credits/reset", { method: "POST" });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "Не удалось сбросить demo credits.");
        }
        setCredits(payload.balance);
      } catch (error) {
        setCredits(5);
      }
    }

    function canSpendCredits(cost, statusElement, featureName) {
      if (creditBalance >= cost) {
        return true;
      }
      statusElement.textContent = t("credits.insufficient", { feature: featureName, cost });
      tabButtons.forEach((item) => item.classList.toggle("active", item.dataset.tab === "pricingPanel"));
      panels.forEach((panel) => panel.classList.toggle("active", panel.id === "pricingPanel"));
      return false;
    }

    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        tabButtons.forEach((item) => item.classList.toggle("active", item === button));
        panels.forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.tab));
      });
    });

    function setFile(file) {
      currentFile = file;
      if (!file) {
        fileTitle.textContent = t("midi.dropTitle");
        fileCopy.textContent = t("midi.dropCopy");
        statusEl.textContent = t("midi.statusEmpty");
        statsEl.innerHTML = "";
        return;
      }
      fileTitle.textContent = file.name;
      fileCopy.textContent = `${Math.max(1, Math.round(file.size / 1024))} KB`;
      statusEl.textContent = t("midi.ready");
      statsEl.innerHTML = "";
    }

    function setFamily(family) {
      currentFamily = family;
      familyButtons.forEach((button) => button.classList.toggle("active", button.dataset.family === family));
      familyCopyEl.textContent = t(familyHints[family]);
      if (!styleTouched && familyStyleDefaults[family]) {
        style.value = familyStyleDefaults[family];
      }
    }

    function renderStats(stats, instrumentFamily) {
      const items = [
        [currentLanguage === "en" ? "Family" : "Тип партии", instrumentFamily],
        [currentLanguage === "en" ? "Style" : "Стиль", stats.style],
        [currentLanguage === "en" ? "Key center" : "Тональный центр", stats.detected_key_center],
        [currentLanguage === "en" ? "Grid" : "Сетка", `${stats.quantize_grid} ${currentLanguage === "en" ? "ticks" : "тиков"}`],
        [currentLanguage === "en" ? "Notes" : "Ноты", `${stats.original_note_count} -> ${stats.edited_note_count}`],
        [currentLanguage === "en" ? "Range" : "Диапазон", `${stats.original_pitch_range[0]}-${stats.original_pitch_range[1]} -> ${stats.edited_pitch_range[0]}-${stats.edited_pitch_range[1]}`],
        [currentLanguage === "en" ? "Average duration" : "Средняя длительность", `${stats.average_original_duration} -> ${stats.average_edited_duration}`],
      ];
      statsEl.innerHTML = items.map(([label, value]) => (
        `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`
      )).join("");
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function downloadBase64Midi(filename, base64Data) {
      downloadBase64File(filename, base64Data, "audio/midi");
    }

    function downloadBase64File(filename, base64Data, mimeType) {
      const blob = base64ToBlob(base64Data, mimeType);
      downloadBlob(filename, blob);
    }

    function base64ToBlob(base64Data, mimeType) {
      const raw = atob(base64Data);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i += 1) {
        bytes[i] = raw.charCodeAt(i);
      }
      return new Blob([bytes], { type: mimeType });
    }

    function downloadBlob(filename, blob) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function downloadTextFile(filename, content, mimeType) {
      downloadBlob(filename, new Blob([content], { type: `${mimeType};charset=utf-8` }));
    }

    function setAudioFiles(files) {
      currentAudioFiles = Array.from(files || []).filter((file) => (
        file.name.toLowerCase().endsWith(".wav")
      ));
      if (!currentAudioFiles.length) {
        audioFileTitle.textContent = t("audio.dropTitle");
        audioFileCopy.textContent = t("audio.dropCopy");
        audioStatusEl.textContent = t("audio.statusEmpty");
        audioFileList.innerHTML = "";
        audioStatsEl.innerHTML = "";
        clearMasterPreview();
        return;
      }

      const totalSize = currentAudioFiles.reduce((sum, file) => sum + file.size, 0);
      audioFileTitle.textContent = currentLanguage === "en"
        ? `${currentAudioFiles.length} WAV stem(s) selected`
        : `${currentAudioFiles.length} WAV stem(s) выбрано`;
      audioFileCopy.textContent = `${Math.max(1, Math.round(totalSize / 1024 / 1024))} MB total`;
      audioStatusEl.textContent = t("audio.ready");
      audioStatsEl.innerHTML = "";
      clearMasterPreview();
      audioFileList.innerHTML = currentAudioFiles.map((file) => (
        `<div class="file-item"><span>${escapeHtml(file.name)}</span><strong>${Math.max(1, Math.round(file.size / 1024))} KB</strong></div>`
      )).join("");
    }

    function renderAudioStats(payload) {
      const roles = payload.stems.map((stem) => `${stem.filename}: ${stem.role}`).join(", ");
      const loudness = payload.loudness || {};
      const masterLoudness = loudness.master || {};
      const premasterLoudness = loudness.premaster || {};
      const items = [
        [currentLanguage === "en" ? "Genre" : "Жанр", payload.genre],
        [currentLanguage === "en" ? "Stems" : "Дорожки", payload.stems.length],
        [currentLanguage === "en" ? "Sample rate" : "Частота дискретизации", `${payload.sample_rate} Hz`],
        [currentLanguage === "en" ? "Premaster LUFS" : "LUFS до мастера", formatLoudness(premasterLoudness.integrated_lufs)],
        [currentLanguage === "en" ? "Master LUFS" : "LUFS мастера", formatLoudness(masterLoudness.integrated_lufs)],
        [currentLanguage === "en" ? "True peak" : "Истинный пик", formatTruePeak(masterLoudness.true_peak_dbtp)],
        [currentLanguage === "en" ? "Loudness method" : "Метод громкости", masterLoudness.method || (currentLanguage === "en" ? "unknown" : "неизвестно")],
        [currentLanguage === "en" ? "Master" : "Мастер", payload.filename],
        [currentLanguage === "en" ? "Roles" : "Роли", roles],
      ];
      audioStatsEl.innerHTML = items.map(([label, value]) => (
        `<div class="stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
      )).join("");
    }

    function formatLoudness(value) {
      return Number.isFinite(value) ? `${value} LUFS` : "n/a";
    }

    function formatTruePeak(value) {
      return Number.isFinite(value) ? `${value} dBTP` : "n/a";
    }

    function clearMasterPreview() {
      currentMaster = null;
      masterAudio.removeAttribute("src");
      roughAudio.removeAttribute("src");
      masterAudio.load();
      roughAudio.load();
      masterPreview.classList.remove("active");
      masterPreviewMeta.textContent = currentLanguage === "en" ? "24-bit WAV" : "24-бит WAV";
    }

    function showMasterPreview(result) {
      currentMaster = {
        filename: result.filename || "master.wav",
        masterUrl: result.files.master,
        roughUrl: result.files.rough,
        mixPlanUrl: result.files.mix_plan,
        analysisUrl: result.files.analysis,
      };
      roughAudio.src = result.files.rough;
      masterAudio.src = result.files.master;
      masterPreviewMeta.textContent = `${result.sample_rate} Hz`;
      masterPreview.classList.add("active");
    }

    async function pollAudioJob(jobId) {
      while (true) {
        const response = await fetch(`/api/audio/jobs/${jobId}`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || (currentLanguage === "en" ? "Could not get job status." : "Не удалось получить статус задачи."));
        }
        if (payload.status === "done") {
          return payload;
        }
        if (payload.status === "failed") {
          throw new Error(payload.error || (currentLanguage === "en" ? "Render failed." : "Рендер завершился ошибкой."));
        }
        audioStatusEl.textContent = payload.status === "running"
          ? t("audio.running")
          : t("audio.queued");
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }

    async function submit() {
      if (!currentFile) {
        statusEl.textContent = t("midi.pickFirst");
        return;
      }
      if (!canSpendCredits(1, statusEl, t("feature.midi"))) {
        return;
      }

      submitButton.disabled = true;
      statusEl.textContent = t("midi.processing");
      statsEl.innerHTML = "";

      const formData = new FormData();
      formData.append("file", currentFile);
      formData.append("instrument_family", currentFamily);
      formData.append("style", style.value);
      formData.append("output_format", outputFormat.value);
      formData.append("include_track_titles", includeTitles.checked ? "true" : "false");

      try {
        const response = await fetch("/api/midi/fix", { method: "POST", body: formData });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || (currentLanguage === "en" ? "Could not process MIDI." : "Не удалось обработать MIDI."));
        }

        renderStats(payload.stats, payload.instrument_family);
        setCredits(payload.credits_remaining ?? creditBalance - 1);
        downloadBase64Midi(payload.filename, payload.midi_base64);
        statusEl.textContent = t("midi.done", { filename: payload.filename });
      } catch (error) {
        statusEl.textContent = error.message || (currentLanguage === "en" ? "Processing error." : "Ошибка обработки.");
      } finally {
        submitButton.disabled = false;
      }
    }

    async function submitAudio() {
      if (!currentAudioFiles.length) {
        audioStatusEl.textContent = t("audio.pickFirst");
        return;
      }
      if (!canSpendCredits(5, audioStatusEl, t("feature.audio"))) {
        return;
      }

      audioSubmitButton.disabled = true;
      audioStatusEl.textContent = t("audio.processing");
      audioStatsEl.innerHTML = "";
      clearMasterPreview();

      const formData = new FormData();
      currentAudioFiles.forEach((file) => formData.append("files", file));
      formData.append("genre", audioGenre.value);
      formData.append("target", masterTarget.value);

      try {
        const response = await fetch("/api/audio/jobs", { method: "POST", body: formData });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || (currentLanguage === "en" ? "Could not process WAV stems." : "Не удалось обработать WAV-дорожки."));
        }

        audioStatusEl.textContent = t("audio.created", { id: payload.id });
        const completedJob = await pollAudioJob(payload.id);
        renderAudioStats(completedJob.result);
        showMasterPreview(completedJob.result);
        setCredits(payload.credits_remaining ?? creditBalance - 5);
        if (completedJob.warnings && completedJob.warnings.length) {
          audioStatusEl.textContent = `${t("audio.done")} ${completedJob.warnings.join(" ")}`;
        } else {
          audioStatusEl.textContent = t("audio.done");
        }
      } catch (error) {
        audioStatusEl.textContent = error.message || (currentLanguage === "en" ? "Processing error." : "Ошибка обработки.");
      } finally {
        audioSubmitButton.disabled = false;
      }
    }

    fileInput.addEventListener("change", (event) => {
      setFile(event.target.files && event.target.files[0] ? event.target.files[0] : null);
    });

    languageButtons.forEach((button) => {
      button.addEventListener("click", () => {
        applyLanguage(button.dataset.lang);
      });
    });

    familyButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setFamily(button.dataset.family);
      });
    });

    style.addEventListener("change", () => {
      styleTouched = true;
    });

    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("drag");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("drag");
    });

    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("drag");
      const [file] = event.dataTransfer.files;
      if (file) {
        fileInput.files = event.dataTransfer.files;
        setFile(file);
      }
    });

    submitButton.addEventListener("click", submit);

    creditPackButtons.forEach((button) => {
      button.addEventListener("click", () => {
        addCredits(Number(button.dataset.credits || "0"));
      });
    });

    resetCreditsButtons.forEach((button) => {
      button.addEventListener("click", () => {
        resetCredits();
      });
    });

    audioInput.addEventListener("change", (event) => {
      setAudioFiles(event.target.files || []);
    });

    audioDropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      audioDropzone.classList.add("drag");
    });

    audioDropzone.addEventListener("dragleave", () => {
      audioDropzone.classList.remove("drag");
    });

    audioDropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      audioDropzone.classList.remove("drag");
      if (event.dataTransfer.files.length) {
        audioInput.files = event.dataTransfer.files;
        setAudioFiles(event.dataTransfer.files);
      }
    });

    audioSubmitButton.addEventListener("click", submitAudio);
    downloadMasterButton.addEventListener("click", () => {
      if (currentMaster) {
        window.location.href = currentMaster.masterUrl;
      }
    });
    downloadMixPlanButton.addEventListener("click", () => {
      if (currentMaster && currentMaster.mixPlanUrl) {
        window.location.href = currentMaster.mixPlanUrl;
      }
    });
    downloadAnalysisButton.addEventListener("click", () => {
      if (currentMaster && currentMaster.analysisUrl) {
        window.location.href = currentMaster.analysisUrl;
      }
    });
    applyLanguage(currentLanguage);
    setCredits(creditBalance);
    refreshCredits();
  </script>
</body>
</html>
"""


V2_CSS = """
    :root {
      --bg: #030509;
      --panel: rgba(255, 255, 255, 0.075);
      --panel-strong: rgba(255, 255, 255, 0.12);
      --line: rgba(255, 255, 255, 0.14);
      --ink: #f7f7fb;
      --muted: rgba(247, 247, 251, 0.62);
      --muted-2: rgba(247, 247, 251, 0.42);
      --accent: #ff4f91;
      --accent-2: #38d7ff;
      --accent-3: #b8ff5c;
      --shadow: 0 30px 120px rgba(0, 0, 0, 0.55);
    }

    * { box-sizing: border-box; }

    html {
      background: var(--bg);
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 50% -12%, rgba(255, 79, 145, 0.22), transparent 30%),
        radial-gradient(circle at 18% 16%, rgba(56, 215, 255, 0.12), transparent 22%),
        radial-gradient(circle at 82% 18%, rgba(184, 255, 92, 0.09), transparent 20%),
        linear-gradient(180deg, #05070c 0%, #010205 100%);
      overflow-x: hidden;
    }

    a { color: inherit; text-decoration: none; }

    .noise {
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.18;
      background-image:
        linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px);
      background-size: 72px 72px;
      mask-image: radial-gradient(circle at center, black, transparent 74%);
      z-index: 0;
    }

    .page {
      position: relative;
      z-index: 1;
      width: min(1180px, calc(100% - 40px));
      margin: 0 auto;
      padding: 28px 0 72px;
    }

    .nav {
      position: sticky;
      top: 18px;
      z-index: 10;
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 18px;
      padding: 10px 0;
    }

    .brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }

    .brand-mark {
      width: 34px;
      height: 34px;
      border-radius: 12px;
      background:
        radial-gradient(circle at 30% 25%, #fff, rgba(255,255,255,0.3) 22%, transparent 24%),
        linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 34px rgba(255, 79, 145, 0.35);
    }

    .nav-pill,
    .actions {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    .nav-pill {
      justify-self: center;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), var(--shadow);
      backdrop-filter: blur(18px);
    }

    .nav-pill a {
      padding: 9px 13px;
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .nav-pill a.active,
    .nav-pill a:hover {
      color: var(--ink);
      background: rgba(255,255,255,0.1);
    }

    .actions {
      justify-self: end;
    }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 42px;
      padding: 0 16px;
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      color: var(--ink);
      font-size: 12px;
      font-weight: 850;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      cursor: pointer;
    }

    .button.primary {
      background: #fff;
      color: #05070c;
      box-shadow: 0 14px 50px rgba(255,255,255,0.18);
    }

    .hero {
      min-height: 760px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 78px 0 28px;
      position: relative;
    }

    .hero::before {
      content: "";
      position: absolute;
      top: 42px;
      left: 50%;
      width: min(720px, 92vw);
      height: min(720px, 92vw);
      border-radius: 50%;
      transform: translateX(-50%);
      background:
        radial-gradient(circle, rgba(255,255,255,0.08), transparent 54%),
        conic-gradient(from 190deg, transparent, rgba(255,79,145,0.18), rgba(56,215,255,0.15), transparent);
      filter: blur(18px);
      opacity: 0.85;
      z-index: -1;
    }

    .micro-logo {
      width: 46px;
      height: 22px;
      margin: 0 auto 38px;
      position: relative;
      opacity: 0.86;
    }

    .micro-logo::before,
    .micro-logo::after {
      content: "";
      position: absolute;
      top: 4px;
      width: 14px;
      height: 14px;
      border: 2px solid rgba(255,255,255,0.82);
      border-radius: 50%;
    }

    .micro-logo::before { left: 6px; }
    .micro-logo::after { right: 6px; }

    .micro-logo span {
      position: absolute;
      left: 20px;
      top: 10px;
      width: 7px;
      height: 2px;
      background: rgba(255,255,255,0.82);
    }

    .orbit {
      position: relative;
      height: 300px;
      width: min(920px, 100%);
      margin: 0 auto 38px;
      perspective: 900px;
    }

    .tile {
      position: absolute;
      left: 50%;
      top: 52%;
      width: 188px;
      height: 188px;
      border: 1px solid rgba(255,255,255,0.18);
      border-radius: 30px;
      overflow: hidden;
      box-shadow: 0 28px 90px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.16);
      transform: translate(-50%, -50%);
      background: var(--panel);
    }

    .tile::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 28% 20%, rgba(255,255,255,0.9), transparent 13%),
        radial-gradient(circle at 70% 28%, rgba(255,255,255,0.45), transparent 16%),
        var(--tile-bg);
      mix-blend-mode: screen;
    }

    .tile::after {
      content: attr(data-label);
      position: absolute;
      left: 14px;
      bottom: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(0,0,0,0.36);
      color: rgba(255,255,255,0.84);
      font-size: 11px;
      font-weight: 800;
      backdrop-filter: blur(12px);
    }

    .tile-1 { --tile-bg: linear-gradient(135deg, #08162f, #1254ff 55%, #30ff9f); transform: translate(-420px, -18px) rotate(-14deg) scale(0.62); opacity: 0.36; }
    .tile-2 { --tile-bg: linear-gradient(135deg, #0d1531, #44e7ff 40%, #ffe95a); transform: translate(-315px, 10px) rotate(-11deg) scale(0.82); opacity: 0.72; }
    .tile-3 { --tile-bg: linear-gradient(135deg, #1b0716, #ff3d83 45%, #1d0a24); transform: translate(-168px, -22px) rotate(-6deg) scale(1.02); }
    .tile-4 { --tile-bg: linear-gradient(135deg, #ff2e78, #311428 58%, #12080f); transform: translate(-50%, -50%) rotate(0deg) scale(1.2); z-index: 4; }
    .tile-5 { --tile-bg: linear-gradient(135deg, #0c5bff, #ff9a27 45%, #fff25c); transform: translate(98px, -22px) rotate(8deg) scale(1.02); }
    .tile-6 { --tile-bg: linear-gradient(135deg, #042a20, #00c987 48%, #ff2b6c); transform: translate(252px, 10px) rotate(13deg) scale(0.82); opacity: 0.72; }
    .tile-7 { --tile-bg: linear-gradient(135deg, #080a14, #0f4cff, #34e8ff); transform: translate(386px, 18px) rotate(17deg) scale(0.62); opacity: 0.34; }

    .hero h1 {
      margin: 0;
      font-size: clamp(44px, 8vw, 104px);
      line-height: 0.88;
      letter-spacing: -0.075em;
      font-weight: 870;
      text-wrap: balance;
    }

    .hero p {
      max-width: 670px;
      margin: 22px auto 0;
      color: var(--muted);
      font-size: clamp(16px, 2vw, 20px);
      line-height: 1.55;
    }

    .hero-actions {
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 30px;
    }

    .section {
      padding: 72px 0 0;
    }

    .section-head {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 22px;
    }

    .section h2 {
      margin: 0;
      font-size: clamp(34px, 5vw, 64px);
      line-height: 0.96;
      letter-spacing: -0.055em;
    }

    .section-copy {
      max-width: 480px;
      color: var(--muted);
      line-height: 1.55;
    }

    .catalog {
      position: relative;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 34px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.035)),
        radial-gradient(circle at 50% 0%, rgba(56,215,255,0.14), transparent 38%);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .catalog::after {
      content: "";
      position: absolute;
      left: 8%;
      right: 8%;
      top: 124px;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.32), transparent);
      opacity: 0.45;
    }

    .module-card,
    .price-card-v2,
    .flow-card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.095), rgba(255,255,255,0.045));
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);
      backdrop-filter: blur(18px);
    }

    .module-card {
      min-height: 188px;
      padding: 18px;
      position: relative;
      overflow: hidden;
    }

    .module-card::before {
      content: "";
      position: absolute;
      width: 96px;
      height: 96px;
      right: -22px;
      top: -20px;
      border-radius: 28px;
      background: var(--icon-bg);
      filter: blur(0.2px);
      box-shadow: 0 22px 46px rgba(0,0,0,0.28);
      transform: rotate(-10deg);
    }

    .module-card strong,
    .price-card-v2 strong {
      display: block;
      margin-bottom: 10px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }

    .module-card p,
    .price-card-v2 p,
    .flow-card p {
      color: var(--muted);
      line-height: 1.48;
      margin: 0;
      font-size: 14px;
    }

    .tag-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 20px 0 0;
    }

    .tag {
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: rgba(255,255,255,0.72);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      background: rgba(255,255,255,0.045);
    }

    .flow {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }

    .flow-card {
      min-height: 238px;
      padding: 24px;
    }

    .step {
      display: inline-flex;
      width: 40px;
      height: 40px;
      align-items: center;
      justify-content: center;
      margin-bottom: 30px;
      border-radius: 14px;
      background: #fff;
      color: #05070c;
      font-weight: 900;
    }

    .pricing-hero {
      padding: 86px 0 36px;
      text-align: center;
    }

    .pricing-hero h1 {
      max-width: 900px;
      margin: 0 auto;
      font-size: clamp(48px, 8vw, 104px);
      line-height: 0.88;
      letter-spacing: -0.075em;
    }

    .pricing-hero p {
      max-width: 620px;
      margin: 22px auto 0;
      color: var(--muted);
      line-height: 1.58;
      font-size: 18px;
    }

    .pricing-grid-v2 {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-top: 34px;
    }

    .price-card-v2 {
      min-height: 390px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
    }

    .price-card-v2.featured {
      border-color: rgba(255,255,255,0.34);
      background:
        radial-gradient(circle at 50% 0%, rgba(255,79,145,0.24), transparent 48%),
        linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.06));
      transform: translateY(-12px);
    }

    .price {
      margin: 20px 0 6px;
      font-size: 44px;
      font-weight: 900;
      letter-spacing: -0.06em;
    }

    .period {
      color: var(--muted-2);
      font-size: 13px;
      font-weight: 750;
    }

    .price-card-v2 ul {
      display: grid;
      gap: 12px;
      margin: 26px 0;
      padding: 0;
      list-style: none;
      color: rgba(255,255,255,0.72);
      font-size: 14px;
      line-height: 1.35;
    }

    .price-card-v2 li::before {
      content: "✦";
      color: var(--accent-3);
      margin-right: 8px;
    }

    .price-card-v2 .button {
      margin-top: auto;
      width: 100%;
    }

    .back-link {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }

    @media (max-width: 780px) {
      .nav {
        grid-template-columns: 1fr;
        justify-items: center;
      }

      .actions {
        justify-self: center;
      }

      .orbit {
        height: 250px;
        transform: scale(0.82);
      }

      .catalog,
      .pricing-grid-v2,
      .flow {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 640px) {
      .page {
        width: min(100% - 28px, 1180px);
        padding-top: 16px;
      }

      .nav-pill {
        width: 100%;
        justify-content: center;
        overflow-x: auto;
      }

      .nav-pill a {
        white-space: nowrap;
      }

      .hero {
        min-height: 670px;
        padding-top: 48px;
      }

      .orbit {
        width: 760px;
        margin-left: 50%;
        transform: translateX(-50%) scale(0.64);
      }

      .section-head {
        display: block;
      }

      .catalog,
      .pricing-grid-v2,
      .flow {
        grid-template-columns: 1fr;
      }

      .price-card-v2.featured {
        transform: none;
      }
    }
"""


V2_HOME_HTML = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>iMixing Studio AI · Design v2</title>
  <style>{V2_CSS}</style>
</head>
<body>
  <div class="noise"></div>
  <main class="page">
    <nav class="nav" aria-label="Main navigation">
      <a class="brand" href="/v2"><span class="brand-mark" aria-hidden="true"></span><span>iMixing</span></a>
      <div class="nav-pill">
        <a class="active" href="/v2">Features</a>
        <a href="#modules">Modules</a>
        <a href="#workflow">Workflow</a>
        <a href="/v2/pricing">Pricing</a>
      </div>
      <div class="actions">
        <a class="button" href="/">Design 1.0</a>
        <a class="button primary" href="#modules">Get Started</a>
      </div>
    </nav>

    <section class="hero">
      <div>
        <div class="micro-logo" aria-hidden="true"><span></span></div>
        <div class="orbit" aria-label="AI music modules">
          <div class="tile tile-1" data-label="Drums"></div>
          <div class="tile tile-2" data-label="Bass"></div>
          <div class="tile tile-3" data-label="Vocal"></div>
          <div class="tile tile-4" data-label="Master"></div>
          <div class="tile tile-5" data-label="MIDI"></div>
          <div class="tile tile-6" data-label="Mix"></div>
          <div class="tile tile-7" data-label="Export"></div>
        </div>
        <h1>Studio sound, without studio friction.</h1>
        <p>
          Новый визуальный вариант iMixing: тёмная premium-сцена, модульные AI-доктора для MIDI и аудио, быстрый путь от черновых дорожек к готовому master.wav.
        </p>
        <div class="hero-actions">
          <a class="button primary" href="/v2/pricing">Explore Pricing</a>
          <a class="button" href="/">Open Design 1.0</a>
        </div>
      </div>
    </section>

    <section class="section" id="modules">
      <div class="section-head">
        <h2>AI modules catalog</h2>
        <p class="section-copy">Как в референсе с каталогом интеграций: каждый модуль — отдельный “инструмент” сервиса, который можно монетизировать и развивать независимо.</p>
      </div>
      <div class="catalog">
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #ff4f91, #5a1dff);">
          <strong>MIDI Doctor</strong>
          <p>Исправляет ноты, длительности, квантайз, velocity и музыкальную читаемость партии.</p>
          <div class="tag-row"><span class="tag">1 credit</span><span class="tag">Live</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #38d7ff, #0c5bff);">
          <strong>Mix & Master</strong>
          <p>Принимает stems, строит rough mix, делает loudness/true peak и отдаёт master.wav.</p>
          <div class="tag-row"><span class="tag">5 credits</span><span class="tag">WAV</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #b8ff5c, #00c987);">
          <strong>Bass Doctor</strong>
          <p>Будущий модуль для грува, басовой логики, сайдчейна и плотности low-end.</p>
          <div class="tag-row"><span class="tag">Soon</span><span class="tag">Paid</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #ff9a27, #fff25c);">
          <strong>Drum Doctor</strong>
          <p>Акценты, ghost notes, humanize, groove maps и жанровая сборка барабанной партии.</p>
          <div class="tag-row"><span class="tag">Soon</span><span class="tag">Pro</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #ffffff, #8d95a6);">
          <strong>Reference Match</strong>
          <p>Сравнение с референсом: тональный баланс, loudness, динамика и stereo image.</p>
          <div class="tag-row"><span class="tag">Roadmap</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #1bffce, #7547ff);">
          <strong>A/B Preview</strong>
          <p>Быстрая проверка rough mix против master, чтобы пользователь слышал ценность сразу.</p>
          <div class="tag-row"><span class="tag">Live</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #ff2e2e, #ff8a00);">
          <strong>Vocal Polish</strong>
          <p>Планируемая цепочка для vocal cleanup, presence, de-essing и лёгкой glue-компрессии.</p>
          <div class="tag-row"><span class="tag">Soon</span></div>
        </article>
        <article class="module-card" style="--icon-bg: linear-gradient(135deg, #2339ff, #b4e9ff);">
          <strong>Project Memory</strong>
          <p>История проектов, версии, повторные экспорты и командный handoff для paid-планов.</p>
          <div class="tag-row"><span class="tag">Paid</span></div>
        </article>
      </div>
    </section>

    <section class="section" id="workflow">
      <div class="section-head">
        <h2>Three-step release flow</h2>
        <p class="section-copy">Страница v2 показывает сервис не как форму загрузки, а как продуктовый workflow для музыканта.</p>
      </div>
      <div class="flow">
        <article class="flow-card">
          <span class="step">01</span>
          <h3>Upload stems or MIDI</h3>
          <p>Пользователь загружает отдельные дорожки, MIDI или набросок партии без сложных настроек.</p>
        </article>
        <article class="flow-card">
          <span class="step">02</span>
          <h3>AI doctors repair the session</h3>
          <p>Сервис применяет музыкальные правила, анализ loudness, роли дорожек и жанровый preset.</p>
        </article>
        <article class="flow-card">
          <span class="step">03</span>
          <h3>Export release-ready files</h3>
          <p>Готовый MIDI, rough mix, master.wav, analysis.json и studio plan доступны из одного проекта.</p>
        </article>
      </div>
    </section>
  </main>
</body>
</html>
"""


V2_PRICING_HTML = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>iMixing Pricing · Design v2</title>
  <style>{V2_CSS}</style>
</head>
<body>
  <div class="noise"></div>
  <main class="page">
    <nav class="nav" aria-label="Main navigation">
      <a class="brand" href="/v2"><span class="brand-mark" aria-hidden="true"></span><span>iMixing</span></a>
      <div class="nav-pill">
        <a href="/v2">Features</a>
        <a href="/v2#modules">Modules</a>
        <a href="/v2#workflow">Workflow</a>
        <a class="active" href="/v2/pricing">Pricing</a>
      </div>
      <div class="actions">
        <a class="button" href="/">Design 1.0</a>
        <a class="button primary" href="/v2">Enter Studio</a>
      </div>
    </nav>

    <section class="pricing-hero">
      <div class="micro-logo" aria-hidden="true"><span></span></div>
      <h1>Pricing that scales from sketch to release.</h1>
      <p>От бесплатного MIDI-doctor до полноценных audio minutes, priority queue и будущих платных AI-докторов для bass, drums, vocal и reference matching.</p>
    </section>

    <section class="pricing-grid-v2" aria-label="Pricing plans">
      <article class="price-card-v2">
        <span class="tag">Free</span>
        <strong>Sketch</strong>
        <p>Для первой проверки идеи и низкого барьера входа.</p>
        <div class="price">$0</div>
        <div class="period">5 demo credits</div>
        <ul>
          <li>15 MIDI exports per month</li>
          <li>1 short audio demo</li>
          <li>Standard queue</li>
          <li>No project history</li>
        </ul>
        <a class="button" href="/">Try v1 app</a>
      </article>

      <article class="price-card-v2 featured">
        <span class="tag">Most popular</span>
        <strong>Creator</strong>
        <p>Для сольных продюсеров, которые часто чистят MIDI и делают masters.</p>
        <div class="price">$12</div>
        <div class="period">per month · 80 demo credits</div>
        <ul>
          <li>300 MIDI exports</li>
          <li>30 audio minutes</li>
          <li>A/B previews</li>
          <li>30-day project history</li>
        </ul>
        <a class="button primary" href="/">Start Creator</a>
      </article>

      <article class="price-card-v2">
        <span class="tag">Release</span>
        <strong>Pro</strong>
        <p>Для активного release workflow, batch-версий и будущих продвинутых докторов.</p>
        <div class="price">$29</div>
        <div class="period">per month · 240 demo credits</div>
        <ul>
          <li>Unlimited MIDI fair use</li>
          <li>180 audio minutes</li>
          <li>Priority queue</li>
          <li>Reference-style modes first</li>
        </ul>
        <a class="button" href="/">Start Pro</a>
      </article>

      <article class="price-card-v2">
        <span class="tag">Teams</span>
        <strong>Studio</strong>
        <p>Для команд, small studios и клиентских проектов с большим объёмом stems.</p>
        <div class="price">$79</div>
        <div class="period">per month · 720 demo credits</div>
        <ul>
          <li>3 seats included</li>
          <li>600 audio minutes</li>
          <li>Larger file limits</li>
          <li>Team project library</li>
        </ul>
        <a class="button" href="/">Talk to Studio</a>
      </article>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Credit logic</h2>
        <p class="section-copy">Эта страница — новый визуальный слой. Реальные mock-лимиты уже подключены в v1 API: MIDI списывает 1 credit, Mix & Master списывает 5 credits.</p>
      </div>
      <a class="back-link" href="/v2">← Back to v2 landing</a>
    </section>
  </main>
</body>
</html>
"""


app = FastAPI(title="iMixing MIDI Doctor", version="0.1.0")
MAX_AUDIO_UPLOAD_BYTES = 250 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
FREE_DEMO_CREDITS = 5
MIDI_CREDIT_COST = 1
AUDIO_CREDIT_COST = 5
CREDIT_COOKIE_NAME = "imixing_credit_session"
CREDIT_SESSIONS: dict[str, int] = {}


def resolve_host_port() -> tuple[str, int]:
    host = os.getenv("HOST", "").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000
    if not 1 <= port <= 65535:
        port = 8000
    return host, port


def _resolve_credit_session(response: Response, credit_session: str | None) -> str:
    session_id = credit_session if credit_session in CREDIT_SESSIONS else uuid.uuid4().hex
    if session_id not in CREDIT_SESSIONS:
        CREDIT_SESSIONS[session_id] = FREE_DEMO_CREDITS
        response.set_cookie(
            CREDIT_COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return session_id


def _credit_balance(response: Response, credit_session: str | None) -> int:
    session_id = _resolve_credit_session(response, credit_session)
    return CREDIT_SESSIONS[session_id]


def _add_credits(response: Response, credit_session: str | None, amount: int) -> int:
    if amount <= 0 or amount > 10_000:
        raise HTTPException(status_code=400, detail="Credit amount must be between 1 and 10000.")
    session_id = _resolve_credit_session(response, credit_session)
    CREDIT_SESSIONS[session_id] += amount
    return CREDIT_SESSIONS[session_id]


def _reset_credits(response: Response, credit_session: str | None) -> int:
    session_id = _resolve_credit_session(response, credit_session)
    CREDIT_SESSIONS[session_id] = FREE_DEMO_CREDITS
    return CREDIT_SESSIONS[session_id]


def _spend_credits(response: Response, credit_session: str | None, cost: int, feature_name: str) -> int:
    session_id = _resolve_credit_session(response, credit_session)
    balance = CREDIT_SESSIONS[session_id]
    if balance < cost:
        raise HTTPException(
            status_code=402,
            detail=f"{feature_name} requires {cost} demo credit(s). Current balance: {balance}.",
        )
    CREDIT_SESSIONS[session_id] = balance - cost
    return CREDIT_SESSIONS[session_id]


def _audio_job_response(job_id: str, status: str, *, detail: str | None = None) -> dict[str, str | int]:
    payload: dict[str, str | int] = {
        "id": job_id,
        "status": status,
        "poll_url": f"/api/audio/jobs/{job_id}",
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


async def _enqueue_audio_mix_job(
    *,
    background_tasks: BackgroundTasks,
    files: list[UploadFile],
    genre: str,
    target: str,
) -> dict[str, str | int]:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one WAV stem.")
    if len(files) > 24:
        raise HTTPException(status_code=413, detail="Upload 24 stems or fewer for the MVP service.")
    if genre not in list_audio_genres():
        raise HTTPException(status_code=400, detail="Unsupported audio genre.")

    job = create_audio_job(genre=genre, target=target)
    total_size = 0
    used_names: set[str] = set()

    try:
        for index, upload in enumerate(files, start=1):
            filename = Path(upload.filename or f"stem_{index}.wav").name
            if not filename.lower().endswith(".wav"):
                raise HTTPException(status_code=400, detail="Only WAV stems are supported right now.")

            safe_name = _unique_upload_name(filename, used_names)
            used_names.add(safe_name)
            destination = job.input_dir / safe_name
            written = await _write_upload_stream(upload, destination)
            if written <= 0:
                raise HTTPException(status_code=400, detail=f"{filename} is empty.")
            _validate_uploaded_wav_header(destination, filename)
            total_size += written
            if total_size > MAX_AUDIO_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Total upload is too large for the MVP service.")
    except Exception:
        cleanup_audio_job(job.id)
        raise

    background_tasks.add_task(render_audio_job, job.id)
    return _audio_job_response(job.id, job.status)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.get("/v2", response_class=HTMLResponse)
async def design_v2() -> HTMLResponse:
    return HTMLResponse(V2_HOME_HTML)


@app.get("/v2/pricing", response_class=HTMLResponse)
async def design_v2_pricing() -> HTMLResponse:
    return HTMLResponse(V2_PRICING_HTML)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/credits")
async def get_credits(
    response: Response,
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, int]:
    return {"balance": _credit_balance(response, credit_session)}


@app.post("/api/credits/add")
async def add_credits(
    response: Response,
    amount: int = Body(..., embed=True),
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, int]:
    return {"balance": _add_credits(response, credit_session, amount)}


@app.post("/api/credits/reset")
async def reset_credits(
    response: Response,
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, int]:
    return {"balance": _reset_credits(response, credit_session)}


@app.post("/api/midi/fix")
async def fix_midi(
    response: Response,
    file: UploadFile = File(...),
    instrument_family: str = Form("harmony"),
    style: str = Form("balanced"),
    output_format: int = Form(1),
    include_track_titles: bool = Form(False),
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, object]:
    filename = file.filename or "upload.mid"
    if not filename.lower().endswith((".mid", ".midi")):
        raise HTTPException(status_code=400, detail="Upload a .mid or .midi file.")
    if instrument_family not in list_instrument_family_names():
        raise HTTPException(status_code=400, detail="Unsupported instrument family.")
    if style not in list_style_names():
        raise HTTPException(status_code=400, detail="Unsupported style.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is too large for the MVP service.")

    try:
        result = fix_midi_bytes(
            payload,
            source_name=filename,
            options=MidiFixOptions(
                style=style,
                instrument_family=instrument_family,
                output_format=output_format,
                include_track_titles=include_track_titles,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    credits_remaining = _spend_credits(response, credit_session, MIDI_CREDIT_COST, "MIDI fix")
    return {
        "filename": result.output_filename,
        "edited_title": result.edited_title,
        "instrument_family": instrument_family,
        "stats": asdict(result.stats),
        "midi_base64": base64.b64encode(result.midi_bytes).decode("ascii"),
        "credits_remaining": credits_remaining,
    }


@app.post("/api/audio/mix", status_code=202)
async def mix_audio(
    response: Response,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    genre: str = Form("balanced"),
    target: str = Form("streaming:-14LUFS:-1dBTP"),
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, str | int]:
    if _credit_balance(response, credit_session) < AUDIO_CREDIT_COST:
        raise HTTPException(status_code=402, detail="Mix & Master requires 5 demo credits.")
    payload = await _enqueue_audio_mix_job(
        background_tasks=background_tasks,
        files=files,
        genre=genre,
        target=target,
    )
    payload["credits_remaining"] = _spend_credits(response, credit_session, AUDIO_CREDIT_COST, "Mix & Master")
    payload["detail"] = "Audio mix now runs as an async job. Poll the returned URL and download files when the job is done."
    return payload


@app.post("/api/audio/jobs", status_code=202)
async def create_audio_mix_job(
    response: Response,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    genre: str = Form("balanced"),
    target: str = Form("streaming:-14LUFS:-1dBTP"),
    credit_session: str | None = Cookie(None, alias=CREDIT_COOKIE_NAME),
) -> dict[str, str | int]:
    if _credit_balance(response, credit_session) < AUDIO_CREDIT_COST:
        raise HTTPException(status_code=402, detail="Mix & Master requires 5 demo credits.")
    payload = await _enqueue_audio_mix_job(
        background_tasks=background_tasks,
        files=files,
        genre=genre,
        target=target,
    )
    payload["credits_remaining"] = _spend_credits(response, credit_session, AUDIO_CREDIT_COST, "Mix & Master")
    return payload


@app.get("/api/audio/jobs/{job_id}")
async def get_audio_mix_job(job_id: str) -> JSONResponse:
    job = get_audio_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Audio job not found.")
    return JSONResponse(job.to_dict())


@app.get("/api/audio/jobs/{job_id}/files/{kind}")
async def get_audio_job_file(job_id: str, kind: str) -> FileResponse:
    job = get_audio_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Audio job not found.")
    if job.status != "done":
        raise HTTPException(status_code=409, detail="Audio job is not finished yet.")

    files = {
        "master": ("master.wav", "audio/wav", job.output_dir / "master.wav"),
        "rough": ("rough_mix.wav", "audio/wav", job.output_dir / "rough_mix.wav"),
        "mix-plan": ("mix_plan.md", "text/markdown", job.output_dir / "mix_plan.md"),
        "analysis": ("analysis.json", "application/json", job.output_dir / "analysis.json"),
    }
    if kind not in files:
        raise HTTPException(status_code=404, detail="Unknown job file.")

    filename, media_type, path = files[kind]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Job file is missing.")
    return FileResponse(path, media_type=media_type, filename=filename)


async def _write_upload_stream(upload: UploadFile, destination: Path) -> int:
    written = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            output.write(chunk)
            written += len(chunk)
            if written > MAX_AUDIO_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Uploaded file is too large for the MVP service.")
    return written


def _validate_uploaded_wav_header(path: Path, original_name: str) -> None:
    try:
        with wave.open(str(path), "rb") as wav_file:
            wav_file.getnchannels()
            wav_file.getsampwidth()
            wav_file.getframerate()
            wav_file.getnframes()
    except (wave.Error, EOFError) as error:
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted WAV file: {original_name}") from error


def _unique_upload_name(filename: str, used_names: set[str]) -> str:
    safe_name = filename.replace("/", "_").replace(chr(92), "_")
    if safe_name not in used_names:
        return safe_name
    path = Path(safe_name)
    counter = 2
    while True:
        candidate = f"{path.stem}_{counter}{path.suffix}"
        if candidate not in used_names:
            return candidate
        counter += 1


def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as error:
        raise SystemExit(
            "uvicorn is not installed. Run `pip install -e .` to install web dependencies."
        ) from error

    host, port = resolve_host_port()
    uvicorn.run("imixing_agent.midi_web:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
