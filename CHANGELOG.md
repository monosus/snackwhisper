
# Change log

## [1.1.0] - 2026-05-12
### Added
- ElevenLabs Speech-to-Text (Scribe) API に対応 (scribe_v1 / scribe_v2)
  - 単語レベルのタイムスタンプを利用した文字起こし
  - ネイティブな話者ダイアライゼーション (話者A/B/C... ラベル付け)
  - words[] から SRT/VTT 字幕を自前で構築
  - プロファイルのプロンプトを keyterms (語彙ヒント) として渡す
- 「話者識別」オプションを Gemini に加えて ElevenLabs でも有効化

### Changed
- 設定ダイアログで ElevenLabs プロバイダ用のデフォルトプロンプトを提供
- 出力形式バリデーションのメッセージを更新 (whisper-1 / scribe_v1 / scribe_v2)
- バージョン番号を 1.0.0 から 1.1.0 に更新

### Fixed
- ElevenLabs API キーが models_read 権限を持たない場合に文字起こしが起動できない問題を修正

## [1.0.0] - 2026-05-12
### Added
- Google Gemini API による文字起こしに対応 (gemini-2.5-flash / gemini-2.5-pro / gemini-2.0-flash)
- モデルとAPIキーをプロファイルとして複数登録できる設定ダイアログを追加
- プロファイル別にプロンプトを編集できる項目を追加 (プロバイダごとのデフォルトプロンプト付き)
- 出力形式に md / json / srt / vtt を追加 (srt/vtt は whisper-1 専用)
- 話者識別 / 章立て+Markdown整形 / 要約・TODO付与の出力オプションを追加 (Gemini限定)
- メイン画面のドロップダウンから登録済みモデルを切り替え可能に
- モデルに応じてオプションを自動でグレーアウトするUI制御を追加
- `--debug` フラグでコンソールに進行状況を逐次出力するデバッグモードを追加
- run.bat / run-debug.bat の起動用バッチを追加
- 「このアプリについて」ダイアログを追加 (バージョン番号・ビルド日時を表示)

### Changed
- UI を sv-ttk (Sun Valley) ライトテーマで全面リニューアル
- メインウィンドウをセクション分けしたレイアウトに整理 (リサイズ対応)
- 設定ダイアログを親ウィンドウ中央に表示するよう変更
- バージョン番号を 0.1.4 から 1.0.0 に更新

### Fixed
- httpx 更新に伴う OpenAI クライアント初期化エラー (proxies引数) を修正 (openai を 1.55+ に更新)
- 新 OpenAI SDK で TranscriptionSegment を辞書アクセスしていた不具合を修正
- gpt-4o-*-transcribe モデル選択時にタイムスタンプ取得でエラーになる問題を、UI側で選択不可にして回避
- Gemini で日本語パスのファイルをアップロードする際の UnicodeEncodeError を回避 (ASCII名の一時ファイルにコピー)
- ステータスバーが初期表示で隠れる場合がある問題を修正 (最小サイズと pack順を調整)

## [0.1.4] - 2025-03-23
### Added
- Transcriptionのモデルを選べるドロップダウンを追加
- 従来のwhisper-1に加えて、gpt-4o-transcribe と gpt-4o-mini-transcribe を選べる

### Changed
- バージョン番号を 0.1.3 から 0.1.4 に更新

## [0.1.3] - 2024-06-11
### Added
- デバッグ用のフラグを config.ini から指定する機能を追加

### Fixed
- 長時間の文字起こしでエラーが発生して停止する不具合を修正
- ファイル分割が発生した際のタイムスタンプを修正

## [0.1.2] - 2024-06-09
### Added
- 出力エンコーディングの指定をconfig.iniに追加

## [0.1.1] - 2024-05-22
- first release

# Template
## [version] - DATE
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
