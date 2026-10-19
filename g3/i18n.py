# -*- coding: utf-8 -*-
"""Translations. English is the default; every string is given in all languages
in one row so nothing can be forgotten:  key: (en, tr, de, es, fr, pt, ja, zh)."""

LANGS = [("en", "English"), ("tr", "Türkçe"), ("de", "Deutsch"), ("es", "Español"),
         ("fr", "Français"), ("pt", "Português"), ("ja", "日本語"), ("zh", "简体中文")]
_ORDER = [code for code, _ in LANGS]

S = {
    # ---- connection states (status bar)
    "st_starting": ("Starting", "Başlatılıyor", "Startet", "Iniciando", "Démarrage", "Iniciando", "起動中", "正在启动"),
    "st_searching": ("Waiting for goggles", "Gözlük bekleniyor", "Warte auf Brille", "Esperando gafas", "En attente du casque", "Aguardando óculos", "ゴーグル待機中", "等待眼镜"),
    "st_connected": ("Connected", "Bağlandı", "Verbunden", "Conectado", "Connecté", "Conectado", "接続済み", "已连接"),
    "st_handshaking": ("Waiting for video", "Görüntü bekleniyor", "Warte auf Video", "Esperando vídeo", "En attente de la vidéo", "Aguardando vídeo", "映像待機中", "等待视频"),
    "st_waiting_kf": ("Waiting for keyframe", "Keyframe bekleniyor", "Warte auf Keyframe", "Esperando keyframe", "En attente d'une image clé", "Aguardando keyframe", "キーフレーム待機中", "等待关键帧"),
    "st_live": ("Live", "Canlı", "Live", "En vivo", "En direct", "Ao vivo", "ライブ", "直播中"),
    "st_stalled": ("Signal lost", "Sinyal kesildi", "Signal verloren", "Señal perdida", "Signal perdu", "Sinal perdido", "信号ロスト", "信号丢失"),
    "st_disconnected": ("Disconnected", "Bağlantı koptu", "Getrennt", "Desconectado", "Déconnecté", "Desconectado", "切断", "已断开"),
    "st_needs_admin": ("Permission needed", "İzin gerekiyor", "Berechtigung nötig", "Se necesita permiso", "Autorisation requise", "Permissão necessária", "権限が必要", "需要权限"),
    "st_admin_denied": ("Permission denied", "İzin verilmedi", "Berechtigung verweigert", "Permiso denegado", "Autorisation refusée", "Permissão negada", "権限が拒否されました", "权限被拒绝"),
    "st_error": ("Error", "Hata", "Fehler", "Error", "Erreur", "Erro", "エラー", "错误"),
    "st_helper_gone": ("Stopped", "Durdu", "Gestoppt", "Detenido", "Arrêté", "Parado", "停止", "已停止"),

    # ---- center banners
    "bn_starting_t": ("Starting…", "Başlatılıyor…", "Startet…", "Iniciando…", "Démarrage…", "Iniciando…", "起動中…", "正在启动…"),
    "bn_searching_t": ("Connect your goggles with USB-C", "Gözlüğü USB-C ile bağla", "Brille per USB-C verbinden", "Conecta las gafas por USB-C", "Branchez le casque en USB-C", "Conecte os óculos via USB-C", "ゴーグルをUSB-Cで接続してください", "请用 USB-C 连接眼镜"),
    "bn_searching_b": ("On the goggles: Settings › About › “OTG Wired Connection to Computer” must be on.\nUse a USB-C cable that carries data.",
                       "Gözlükte: Settings › About › “OTG Wired Connection to Computer” açık olmalı.\nVeri taşıyan bir USB-C kablo kullan.",
                       "An der Brille: Settings › About › „OTG Wired Connection to Computer“ muss an sein.\nEin USB-C-Datenkabel verwenden.",
                       "En las gafas: Settings › About › «OTG Wired Connection to Computer» debe estar activado.\nUsa un cable USB-C de datos.",
                       "Sur le casque : Settings › About › « OTG Wired Connection to Computer » doit être activé.\nUtilisez un câble USB-C de données.",
                       "Nos óculos: Settings › About › “OTG Wired Connection to Computer” deve estar ativado.\nUse um cabo USB-C de dados.",
                       "ゴーグル: Settings › About ›「OTG Wired Connection to Computer」をオンにしてください。\nデータ通信対応のUSB-Cケーブルを使用してください。",
                       "眼镜上：Settings › About ›「OTG Wired Connection to Computer」必须开启。\n请使用支持数据传输的 USB-C 线。"),
    "bn_wait_t": ("Goggles connected — waiting for video", "Gözlük bağlı, görüntü bekleniyor", "Brille verbunden – warte auf Video", "Gafas conectadas: esperando vídeo", "Casque connecté — en attente de la vidéo", "Óculos conectados — aguardando vídeo", "ゴーグル接続済み — 映像待機中", "眼镜已连接 — 等待视频"),
    "bn_wait_b": ("Power on the drone and make sure the goggles show a live picture.", "Drone'u aç ve gözlükte canlı görüntü olduğundan emin ol.", "Drohne einschalten und prüfen, dass die Brille ein Live-Bild zeigt.", "Enciende el dron y comprueba que las gafas muestran imagen en directo.", "Allumez le drone et vérifiez que le casque affiche l'image en direct.", "Ligue o drone e confira se os óculos mostram imagem ao vivo.", "ドローンの電源を入れ、ゴーグルにライブ映像が出ていることを確認してください。", "打开无人机，并确认眼镜中有实时画面。"),
    "bn_kf_t": ("Video is arriving — waiting for a keyframe", "Görüntü geliyor, keyframe bekleniyor", "Video kommt an – warte auf Keyframe", "Llega vídeo: esperando un keyframe", "La vidéo arrive — en attente d'une image clé", "O vídeo está chegando — aguardando keyframe", "映像受信中 — キーフレーム待機中", "正在接收视频 — 等待关键帧"),
    "bn_kf_b": ("On the goggles, switch “Share Liveview to Mobile Device via Wi-Fi” off and on again.", "Gözlükte “Share Liveview to Mobile Device via Wi-Fi” ayarını kapatıp tekrar aç.", "An der Brille „Share Liveview to Mobile Device via Wi-Fi“ aus- und wieder einschalten.", "En las gafas, desactiva y vuelve a activar «Share Liveview to Mobile Device via Wi-Fi».", "Sur le casque, désactivez puis réactivez « Share Liveview to Mobile Device via Wi-Fi ».", "Nos óculos, desligue e ligue de novo “Share Liveview to Mobile Device via Wi-Fi”.", "ゴーグルで「Share Liveview to Mobile Device via Wi-Fi」をオフにしてから再度オンにしてください。", "在眼镜上将「Share Liveview to Mobile Device via Wi-Fi」关闭后再打开。"),
    "bn_stalled_t": ("Signal lost", "Sinyal kesildi", "Signal verloren", "Señal perdida", "Signal perdu", "Sinal perdido", "信号ロスト", "信号丢失"),
    "bn_reconnecting": ("Reconnecting…", "Yeniden bağlanılıyor…", "Verbinde erneut…", "Reconectando…", "Reconnexion…", "Reconectando…", "再接続中…", "正在重新连接…"),
    "bn_disc_t": ("Goggles disconnected", "Gözlük bağlantısı koptu", "Brille getrennt", "Gafas desconectadas", "Casque déconnecté", "Óculos desconectados", "ゴーグルが切断されました", "眼镜已断开"),
    "bn_disc_b": ("Check the cable. Reconnecting…", "Kabloyu kontrol et. Yeniden bağlanılıyor…", "Kabel prüfen. Verbinde erneut…", "Revisa el cable. Reconectando…", "Vérifiez le câble. Reconnexion…", "Verifique o cabo. Reconectando…", "ケーブルを確認してください。再接続中…", "请检查数据线。正在重新连接…"),
    "bn_admin_t": ("Administrator permission needed", "Yönetici izni gerekiyor", "Administratorrechte nötig", "Se necesita permiso de administrador", "Autorisation administrateur requise", "Permissão de administrador necessária", "管理者権限が必要です", "需要管理员权限"),
    "bn_admin_b": ("macOS will ask for your password to open the goggles' USB connection.", "Gözlüğün USB bağlantısını açmak için macOS şifreni soracak.", "macOS fragt nach deinem Passwort, um die USB-Verbindung zur Brille zu öffnen.", "macOS pedirá tu contraseña para abrir la conexión USB de las gafas.", "macOS va demander votre mot de passe pour ouvrir la connexion USB du casque.", "O macOS vai pedir sua senha para abrir a conexão USB dos óculos.", "ゴーグルのUSB接続を開くため、macOSがパスワードを求めます。", "macOS 会要求输入密码以打开眼镜的 USB 连接。"),
    "bn_denied_t": ("Permission was not granted", "İzin verilmedi", "Berechtigung wurde nicht erteilt", "No se concedió el permiso", "L'autorisation n'a pas été accordée", "A permissão não foi concedida", "権限が許可されませんでした", "未获得权限"),
    "bn_denied_b": ("Press “Reconnect” to try again.", "Tekrar denemek için “Yeniden bağlan”a bas.", "„Neu verbinden“ drücken, um es erneut zu versuchen.", "Pulsa «Reconectar» para intentarlo de nuevo.", "Cliquez sur « Reconnecter » pour réessayer.", "Clique em “Reconectar” para tentar de novo.", "「再接続」を押してもう一度お試しください。", "点击「重新连接」重试。"),
    "bn_error_t": ("Connection error", "Bağlantı hatası", "Verbindungsfehler", "Error de conexión", "Erreur de connexion", "Erro de conexão", "接続エラー", "连接错误"),
    "bn_gone_t": ("Connection process stopped", "Bağlantı süreci durdu", "Verbindungsprozess beendet", "El proceso de conexión se detuvo", "Le processus de connexion s'est arrêté", "O processo de conexão parou", "接続プロセスが停止しました", "连接进程已停止"),

    # ---- bottom bar
    "btn_rec": ("Record", "Kaydet", "Aufnahme", "Grabar", "Enregistrer", "Gravar", "録画", "录制"),
    "btn_stop": ("Stop", "Durdur", "Stopp", "Detener", "Arrêter", "Parar", "停止", "停止"),
    "btn_golive": ("Go Live", "Yayına Başla", "Live gehen", "Emitir", "Passer en direct", "Iniciar live", "配信開始", "开始直播"),
    "btn_endlive": ("End Live", "Yayını Bitir", "Live beenden", "Terminar", "Arrêter le direct", "Encerrar live", "配信終了", "结束直播"),
    "btn_replay": ("Replay", "Tekrar", "Replay", "Repetición", "Replay", "Replay", "リプレイ", "回放"),
    "btn_snapshot": ("Snapshot", "Fotoğraf", "Foto", "Captura", "Capture", "Captura", "スナップショット", "截图"),
    "btn_fullscreen": ("Full screen", "Tam ekran", "Vollbild", "Pantalla completa", "Plein écran", "Tela cheia", "全画面", "全屏"),
    "btn_reconnect": ("Reconnect", "Yeniden bağlan", "Neu verbinden", "Reconectar", "Reconnecter", "Reconectar", "再接続", "重新连接"),
    "btn_panel": ("Panel", "Panel", "Panel", "Panel", "Panneau", "Painel", "パネル", "面板"),
    "stats_line": ("{fps:.0f} fps · {mbps:.1f} Mbit/s · {dropped} dropped", "{fps:.0f} fps · {mbps:.1f} Mbit/s · {dropped} kayıp", "{fps:.0f} fps · {mbps:.1f} Mbit/s · {dropped} verloren", "{fps:.0f} fps · {mbps:.1f} Mbit/s · {dropped} perdidos", "{fps:.0f} i/s · {mbps:.1f} Mbit/s · {dropped} perdues", "{fps:.0f} fps · {mbps:.1f} Mbit/s · {dropped} perdidos", "{fps:.0f} fps · {mbps:.1f} Mbit/s · ドロップ {dropped}", "{fps:.0f} fps · {mbps:.1f} Mbit/s · 丢帧 {dropped}"),

    # ---- navigation
    "nav_broadcast": ("Broadcast", "Yayın", "Streaming", "Emisión", "Diffusion", "Transmissão", "配信", "直播"),
    "nav_picture": ("Picture", "Görüntü", "Bild", "Imagen", "Image", "Imagem", "映像", "画面"),
    "nav_overlay": ("Overlay", "Overlay", "Overlay", "Superposición", "Incrustation", "Sobreposição", "オーバーレイ", "叠加层"),
    "nav_record": ("Record", "Kayıt", "Aufnahme", "Grabación", "Enregistrement", "Gravação", "録画", "录制"),
    "nav_diag": ("Diagnostics", "Tanılama", "Diagnose", "Diagnóstico", "Diagnostic", "Diagnóstico", "診断", "诊断"),
    "nav_settings": ("Settings", "Ayarlar", "Einstellungen", "Ajustes", "Réglages", "Ajustes", "設定", "设置"),

    # ---- broadcast page
    "bc_destinations": ("Destinations", "Yayın hedefleri", "Ziele", "Destinos", "Destinations", "Destinos", "配信先", "推流目标"),
    "bc_add": ("Add destination", "Hedef ekle", "Ziel hinzufügen", "Añadir destino", "Ajouter une destination", "Adicionar destino", "配信先を追加", "添加目标"),
    "bc_edit": ("Edit", "Düzenle", "Bearbeiten", "Editar", "Modifier", "Editar", "編集", "编辑"),
    "bc_remove": ("Remove", "Kaldır", "Entfernen", "Quitar", "Supprimer", "Remover", "削除", "删除"),
    "bc_none": ("No destinations yet. Add YouTube, Twitch, Facebook, Instagram, Kick or any RTMP server.", "Henüz hedef yok. YouTube, Twitch, Facebook, Instagram, Kick veya herhangi bir RTMP sunucusu ekle.", "Noch keine Ziele. YouTube, Twitch, Facebook, Instagram, Kick oder einen RTMP-Server hinzufügen.", "Aún no hay destinos. Añade YouTube, Twitch, Facebook, Instagram, Kick o cualquier servidor RTMP.", "Aucune destination. Ajoutez YouTube, Twitch, Facebook, Instagram, Kick ou un serveur RTMP.", "Nenhum destino ainda. Adicione YouTube, Twitch, Facebook, Instagram, Kick ou qualquer servidor RTMP.", "配信先がありません。YouTube、Twitch、Facebook、Instagram、Kick、または任意のRTMPサーバーを追加してください。", "还没有目标。可添加 YouTube、Twitch、Facebook、Instagram、Kick 或任意 RTMP 服务器。"),
    "bc_quality": ("Output quality", "Çıkış kalitesi", "Ausgabequalität", "Calidad de salida", "Qualité de sortie", "Qualidade de saída", "出力品質", "输出质量"),
    "bc_resolution": ("Resolution", "Çözünürlük", "Auflösung", "Resolución", "Résolution", "Resolução", "解像度", "分辨率"),
    "bc_bitrate": ("Bitrate", "Bitrate", "Bitrate", "Bitrate", "Débit", "Bitrate", "ビットレート", "码率"),
    "bc_encoder": ("Encoder", "Kodlayıcı", "Encoder", "Codificador", "Encodeur", "Codificador", "エンコーダー", "编码器"),
    "enc_hw": ("Hardware (recommended)", "Donanım (önerilen)", "Hardware (empfohlen)", "Hardware (recomendado)", "Matériel (recommandé)", "Hardware (recomendado)", "ハードウェア（推奨）", "硬件（推荐）"),
    "enc_sw": ("Software (x264)", "Yazılım (x264)", "Software (x264)", "Software (x264)", "Logiciel (x264)", "Software (x264)", "ソフトウェア (x264)", "软件 (x264)"),
    "bc_local": ("Local outputs", "Yerel çıkışlar", "Lokale Ausgaben", "Salidas locales", "Sorties locales", "Saídas locais", "ローカル出力", "本地输出"),
    "bc_obs": ("OBS / VLC (UDP stream)", "OBS / VLC (UDP yayını)", "OBS / VLC (UDP-Stream)", "OBS / VLC (flujo UDP)", "OBS / VLC (flux UDP)", "OBS / VLC (stream UDP)", "OBS / VLC（UDPストリーム）", "OBS / VLC（UDP 流）"),
    "bc_obs_hint": ("In OBS: Sources › Media Source › untick “Local File” › Input:", "OBS'te: Kaynaklar › Medya Kaynağı › “Yerel Dosya” işaretini kaldır › Giriş:", "In OBS: Quellen › Medienquelle › „Lokale Datei“ abwählen › Eingabe:", "En OBS: Fuentes › Fuente multimedia › desmarca «Archivo local» › Entrada:", "Dans OBS : Sources › Source média › décochez « Fichier local » › Entrée :", "No OBS: Fontes › Fonte de mídia › desmarque “Arquivo local” › Entrada:", "OBS: ソース › メディアソース ›「ローカルファイル」のチェックを外す › 入力:", "在 OBS 中：来源 › 媒体源 › 取消勾选「本地文件」› 输入："),
    "bc_web": ("Phone & browser viewer", "Telefon ve tarayıcı izleyici", "Handy- & Browser-Viewer", "Visor para móvil y navegador", "Visionneuse téléphone et navigateur", "Visualizador no celular e navegador", "スマホ・ブラウザビューア", "手机和浏览器观看"),
    "bc_web_hint": ("Open on any device on the same Wi-Fi, or scan the QR code. OBS can use it as a Media Source too.", "Aynı Wi-Fi'daki herhangi bir cihazda aç ya da QR kodu okut. OBS'te Medya Kaynağı olarak da kullanılabilir.", "Auf jedem Gerät im selben WLAN öffnen oder QR-Code scannen. Auch als OBS-Medienquelle nutzbar.", "Ábrelo en cualquier dispositivo de la misma Wi-Fi o escanea el código QR. También sirve como fuente multimedia en OBS.", "Ouvrez-la sur n'importe quel appareil du même Wi-Fi ou scannez le QR code. Utilisable aussi comme source média OBS.", "Abra em qualquer dispositivo na mesma Wi-Fi ou escaneie o QR code. Também funciona como Fonte de mídia no OBS.", "同じWi-Fi上の任意の端末で開くか、QRコードをスキャンしてください。OBSのメディアソースとしても使えます。", "在同一 Wi-Fi 下的任意设备上打开，或扫描二维码。也可作为 OBS 媒体源使用。"),
    "bc_copy": ("Copy", "Kopyala", "Kopieren", "Copiar", "Copier", "Copiar", "コピー", "复制"),
    "bc_copied": ("Copied", "Kopyalandı", "Kopiert", "Copiado", "Copié", "Copiado", "コピーしました", "已复制"),
    "bc_audio": ("Add silent audio track (recommended for YouTube)", "Sessiz ses kanalı ekle (YouTube için önerilir)", "Stille Tonspur hinzufügen (für YouTube empfohlen)", "Añadir pista de audio silenciosa (recomendado para YouTube)", "Ajouter une piste audio silencieuse (recommandé pour YouTube)", "Adicionar faixa de áudio silenciosa (recomendado para YouTube)", "無音の音声トラックを追加（YouTube推奨）", "添加静音音轨（推荐用于 YouTube）"),
    "bc_vertical_hint": ("Tip: Instagram and TikTok look best with 9:16 framing (Picture tab).", "İpucu: Instagram ve TikTok için 9:16 kadraj en iyisi (Görüntü sekmesi).", "Tipp: Instagram und TikTok sehen mit 9:16 am besten aus (Tab „Bild“).", "Consejo: Instagram y TikTok se ven mejor en 9:16 (pestaña Imagen).", "Astuce : Instagram et TikTok sont plus beaux en 9:16 (onglet Image).", "Dica: Instagram e TikTok ficam melhores em 9:16 (aba Imagem).", "ヒント: InstagramやTikTokは9:16がおすすめです（映像タブ）。", "提示：Instagram 和 TikTok 使用 9:16 画幅效果最佳（画面标签页）。"),
    "state_off": ("off", "kapalı", "aus", "apagado", "désactivé", "desligado", "オフ", "关闭"),
    "state_connecting": ("connecting…", "bağlanıyor…", "verbinde…", "conectando…", "connexion…", "conectando…", "接続中…", "连接中…"),
    "state_live": ("live", "canlı", "live", "en vivo", "en direct", "ao vivo", "配信中", "直播中"),
    "state_error": ("error", "hata", "Fehler", "error", "erreur", "erro", "エラー", "错误"),
    "state_waiting": ("waiting for video", "görüntü bekleniyor", "warte auf Video", "esperando vídeo", "en attente de vidéo", "aguardando vídeo", "映像待機中", "等待视频"),
    "live_started": ("Live on {n} destination(s)", "{n} hedefte yayındasın", "Live auf {n} Ziel(en)", "En vivo en {n} destino(s)", "En direct sur {n} destination(s)", "Ao vivo em {n} destino(s)", "{n} 件の配信先でライブ中", "正在向 {n} 个目标直播"),
    "live_ended": ("Live ended", "Yayın bitti", "Live beendet", "Emisión terminada", "Direct terminé", "Live encerrada", "配信を終了しました", "直播已结束"),
    "live_need_dest": ("Add and enable a destination first (Broadcast tab).", "Önce bir hedef ekle ve etkinleştir (Yayın sekmesi).", "Zuerst ein Ziel hinzufügen und aktivieren (Tab „Streaming“).", "Primero añade y activa un destino (pestaña Emisión).", "Ajoutez et activez d'abord une destination (onglet Diffusion).", "Primeiro adicione e ative um destino (aba Transmissão).", "まず配信先を追加して有効にしてください（配信タブ）。", "请先添加并启用一个目标（直播标签页）。"),
    "confirm_end": ("Stop streaming to all destinations?", "Tüm hedeflere yayın durdurulsun mu?", "Streaming zu allen Zielen beenden?", "¿Detener la emisión en todos los destinos?", "Arrêter la diffusion vers toutes les destinations ?", "Parar a transmissão para todos os destinos?", "すべての配信先への配信を停止しますか？", "停止向所有目标推流？"),

    # ---- destination dialog
    "dd_title": ("Destination", "Yayın hedefi", "Ziel", "Destino", "Destination", "Destino", "配信先", "推流目标"),
    "dd_platform": ("Platform", "Platform", "Plattform", "Plataforma", "Plateforme", "Plataforma", "プラットフォーム", "平台"),
    "dd_name": ("Name", "Ad", "Name", "Nombre", "Nom", "Nome", "名前", "名称"),
    "dd_server": ("Server URL", "Sunucu adresi", "Server-URL", "URL del servidor", "URL du serveur", "URL do servidor", "サーバーURL", "服务器地址"),
    "dd_key": ("Stream key", "Yayın anahtarı", "Stream-Key", "Clave de emisión", "Clé de stream", "Chave de transmissão", "ストリームキー", "推流密钥"),
    "dd_show": ("Show", "Göster", "Anzeigen", "Mostrar", "Afficher", "Mostrar", "表示", "显示"),
    "dd_enabled": ("Use when going live", "Yayına başlarken kullan", "Beim Live-Gehen verwenden", "Usar al emitir", "Utiliser lors du direct", "Usar ao iniciar a live", "配信開始時に使用", "开播时使用"),
    "dd_paste_hint": ("Copy the server URL and stream key from the platform's live dashboard.", "Sunucu adresini ve yayın anahtarını platformun canlı yayın panelinden kopyala.", "Server-URL und Stream-Key aus dem Live-Dashboard der Plattform kopieren.", "Copia la URL del servidor y la clave desde el panel en vivo de la plataforma.", "Copiez l'URL du serveur et la clé depuis le tableau de bord live de la plateforme.", "Copie a URL do servidor e a chave no painel de live da plataforma.", "サーバーURLとストリームキーは各プラットフォームのライブ管理画面からコピーしてください。", "从平台的直播后台复制服务器地址和推流密钥。"),
    "dd_custom": ("Custom RTMP / RTMPS", "Özel RTMP / RTMPS", "Eigenes RTMP / RTMPS", "RTMP / RTMPS personalizado", "RTMP / RTMPS personnalisé", "RTMP / RTMPS personalizado", "カスタム RTMP / RTMPS", "自定义 RTMP / RTMPS"),
    "dd_save": ("Save", "Kaydet", "Speichern", "Guardar", "Enregistrer", "Salvar", "保存", "保存"),
    "dd_cancel": ("Cancel", "İptal", "Abbrechen", "Cancelar", "Annuler", "Cancelar", "キャンセル", "取消"),

    # ---- picture page
    "pic_stab": ("Stabilization", "Stabilizasyon", "Stabilisierung", "Estabilización", "Stabilisation", "Estabilização", "手ぶれ補正", "防抖"),
    "pic_stab_hint": ("Computed from the image itself, like RockSteady. Applies to the preview and all outputs.", "RockSteady gibi, doğrudan görüntüden hesaplanır. Önizlemeye ve tüm çıkışlara uygulanır.", "Wird wie RockSteady direkt aus dem Bild berechnet. Gilt für Vorschau und alle Ausgaben.", "Se calcula a partir de la propia imagen, como RockSteady. Se aplica a la vista previa y a todas las salidas.", "Calculée à partir de l'image, comme RockSteady. S'applique à l'aperçu et à toutes les sorties.", "Calculada a partir da própria imagem, como o RockSteady. Vale para a prévia e todas as saídas.", "RockSteadyのように映像そのものから計算します。プレビューとすべての出力に適用されます。", "像 RockSteady 一样直接从画面计算，作用于预览和所有输出。"),
    "stab_off": ("Off", "Kapalı", "Aus", "No", "Désactivée", "Desligada", "オフ", "关闭"),
    "stab_low": ("Low", "Düşük", "Niedrig", "Baja", "Faible", "Baixa", "弱", "低"),
    "stab_medium": ("Medium", "Orta", "Mittel", "Media", "Moyenne", "Média", "中", "中"),
    "stab_high": ("High", "Yüksek", "Hoch", "Alta", "Élevée", "Alta", "強", "高"),
    "stab_max": ("Max", "Maksimum", "Maximal", "Máxima", "Maximale", "Máxima", "最大", "最强"),
    "pic_roll": ("Correct roll (keep horizon steady)", "Yatışı düzelt (ufku sabit tut)", "Rollen korrigieren (Horizont ruhig halten)", "Corregir alabeo (horizonte estable)", "Corriger le roulis (horizon stable)", "Corrigir rolagem (horizonte estável)", "ロール補正（水平を安定）", "校正横滚（稳定地平线）"),
    "pic_lookahead": ("Cinematic smoothing (outputs only)", "Sinematik yumuşatma (sadece çıkışlar)", "Kinoreife Glättung (nur Ausgaben)", "Suavizado cinematográfico (solo salidas)", "Lissage cinéma (sorties uniquement)", "Suavização cinematográfica (só saídas)", "シネマティック補正（出力のみ）", "电影级平滑（仅输出）"),
    "la_off": ("Off", "Kapalı", "Aus", "No", "Désactivé", "Desligado", "オフ", "关闭"),
    "la_05": ("0.5 s delay", "0,5 sn gecikme", "0,5 s Verzögerung", "0,5 s de retardo", "0,5 s de délai", "0,5 s de atraso", "0.5秒遅延", "延迟 0.5 秒"),
    "la_1": ("1 s delay", "1 sn gecikme", "1 s Verzögerung", "1 s de retardo", "1 s de délai", "1 s de atraso", "1秒遅延", "延迟 1 秒"),
    "pic_lookahead_hint": ("Looks at upcoming frames for silkier motion. Only streams and processed recordings are delayed; your preview stays real-time.", "Daha akıcı hareket için sonraki karelere bakar. Sadece yayın ve işlenmiş kayıt gecikir; önizleme gerçek zamanlı kalır.", "Nutzt kommende Bilder für seidigere Bewegung. Nur Streams und bearbeitete Aufnahmen werden verzögert, die Vorschau bleibt in Echtzeit.", "Usa los fotogramas siguientes para un movimiento más suave. Solo se retrasan las emisiones y grabaciones procesadas; la vista previa sigue en tiempo real.", "Utilise les images à venir pour un mouvement plus soyeux. Seuls les flux et enregistrements traités sont retardés ; l'aperçu reste en temps réel.", "Usa os próximos quadros para um movimento mais suave. Só a transmissão e as gravações processadas atrasam; a prévia continua em tempo real.", "先のフレームを使ってより滑らかにします。遅延するのは配信と加工済み録画のみで、プレビューはリアルタイムのままです。", "参考后续帧使画面更顺滑。仅推流和处理后的录制会延迟，预览保持实时。"),
    "pic_framing": ("Framing", "Kadraj", "Bildausschnitt", "Encuadre", "Cadrage", "Enquadramento", "フレーミング", "构图"),
    "pic_aspect": ("Aspect ratio", "En-boy oranı", "Seitenverhältnis", "Relación de aspecto", "Format", "Proporção", "アスペクト比", "画面比例"),
    "pic_pan": ("Horizontal position", "Yatay konum", "Horizontale Position", "Posición horizontal", "Position horizontale", "Posição horizontal", "水平位置", "水平位置"),
    "pic_zoom": ("Zoom", "Yakınlaştırma", "Zoom", "Zoom", "Zoom", "Zoom", "ズーム", "缩放"),
    "pic_rotate": ("Rotate 180° (upside-down camera)", "180° döndür (ters kamera)", "180° drehen (Kamera kopfüber)", "Girar 180° (cámara invertida)", "Pivoter de 180° (caméra à l'envers)", "Girar 180° (câmera invertida)", "180°回転（逆さ取り付け）", "旋转 180°（倒装摄像头）"),
    "pic_mirror": ("Mirror", "Ayna", "Spiegeln", "Espejo", "Miroir", "Espelhar", "ミラー", "镜像"),

    # ---- overlay page
    "ov_elements": ("Elements", "Öğeler", "Elemente", "Elementos", "Éléments", "Elementos", "要素", "元素"),
    "ov_preview": ("Preview", "Önizleme", "Vorschau", "Vista previa", "Aperçu", "Prévia", "プレビュー", "预览"),
    "ov_stream": ("Stream", "Yayın", "Stream", "Emisión", "Flux", "Transmissão", "配信", "推流"),
    "ov_link": ("Link quality", "Bağlantı kalitesi", "Verbindungsqualität", "Calidad del enlace", "Qualité du lien", "Qualidade do link", "リンク品質", "链路质量"),
    "ov_timer": ("Flight timer", "Uçuş süresi", "Flugzeit", "Tiempo de vuelo", "Chrono de vol", "Tempo de voo", "フライトタイマー", "飞行计时"),
    "ov_clock": ("Clock", "Saat", "Uhr", "Reloj", "Horloge", "Relógio", "時計", "时钟"),
    "ov_crosshair": ("Crosshair", "Nişangah", "Fadenkreuz", "Mira", "Réticule", "Mira", "照準", "准星"),
    "ov_grid": ("Grid (thirds)", "Izgara (üçte bir)", "Raster (Drittel)", "Cuadrícula (tercios)", "Grille (tiers)", "Grade (terços)", "グリッド（三分割）", "网格（三分法）"),
    "ov_latency": ("Latency test clock", "Gecikme test saati", "Latenz-Testuhr", "Reloj de prueba de latencia", "Horloge de test de latence", "Relógio de teste de latência", "遅延テスト時計", "延迟测试时钟"),
    "ov_latency_hint": ("Point the drone camera at this screen: the difference between the real clock and the one seen through the camera is your glass-to-glass latency.", "Drone kamerasını bu ekrana çevir: gerçek saat ile kameradan görünen saat arasındaki fark, uçtan uca gecikmendir.", "Drohnenkamera auf diesen Bildschirm richten: Die Differenz zwischen echter Uhr und der Uhr im Kamerabild ist die Ende-zu-Ende-Latenz.", "Apunta la cámara del dron a esta pantalla: la diferencia entre el reloj real y el que ve la cámara es tu latencia total.", "Pointez la caméra du drone vers cet écran : l'écart entre l'horloge réelle et celle vue par la caméra est votre latence de bout en bout.", "Aponte a câmera do drone para esta tela: a diferença entre o relógio real e o visto pela câmera é a sua latência total.", "ドローンのカメラをこの画面に向けてください。実際の時計とカメラ越しの時計の差がエンドツーエンド遅延です。", "将无人机摄像头对准此屏幕：真实时钟与画面中时钟的差值即为端到端延迟。"),
    "ov_watermark": ("Watermark", "Filigran", "Wasserzeichen", "Marca de agua", "Filigrane", "Marca d'água", "ウォーターマーク", "水印"),
    "ov_wm_text": ("Watermark text", "Filigran metni", "Wasserzeichen-Text", "Texto de la marca", "Texte du filigrane", "Texto da marca", "ウォーターマークの文字", "水印文字"),
    "ov_wm_pos": ("Position", "Konum", "Position", "Posición", "Position", "Posição", "位置", "位置"),
    "pos_tl": ("Top left", "Sol üst", "Oben links", "Arriba izquierda", "En haut à gauche", "Superior esquerdo", "左上", "左上"),
    "pos_tr": ("Top right", "Sağ üst", "Oben rechts", "Arriba derecha", "En haut à droite", "Superior direito", "右上", "右上"),
    "pos_bl": ("Bottom left", "Sol alt", "Unten links", "Abajo izquierda", "En bas à gauche", "Inferior esquerdo", "左下", "左下"),
    "pos_br": ("Bottom right", "Sağ alt", "Unten rechts", "Abajo derecha", "En bas à droite", "Inferior direito", "右下", "右下"),
    "ov_osd_note": ("DJI / Betaflight OSD: the goggles draw it on their own screen. If you set the goggles' recording to include the OSD, it may appear in the video here as well. Diagnostics › Telemetry capture can help decode it.", "DJI / Betaflight OSD: gözlük bunu kendi ekranına çiziyor. Gözlüğün kaydını OSD'li moda alırsan burada da videonun içinde görünebilir. Tanılama › Telemetri yakalama çözmeye yardımcı olabilir.", "DJI-/Betaflight-OSD: Die Brille zeichnet es auf ihrem eigenen Bildschirm. Wenn die Aufnahme der Brille das OSD einschließt, kann es auch hier im Video erscheinen. Diagnose › Telemetrie-Mitschnitt hilft beim Entschlüsseln.", "OSD de DJI / Betaflight: las gafas lo dibujan en su propia pantalla. Si la grabación de las gafas incluye el OSD, puede aparecer también aquí en el vídeo. Diagnóstico › Captura de telemetría ayuda a descifrarlo.", "OSD DJI / Betaflight : le casque le dessine sur son propre écran. Si l'enregistrement du casque inclut l'OSD, il peut aussi apparaître ici dans la vidéo. Diagnostic › Capture de télémétrie aide à le décoder.", "OSD DJI / Betaflight: os óculos o desenham na própria tela. Se a gravação dos óculos incluir o OSD, ele pode aparecer aqui no vídeo também. Diagnóstico › Captura de telemetria ajuda a decodificá-lo.", "DJI / Betaflight OSD はゴーグル自身の画面に描画されます。ゴーグルの録画設定でOSDを含めると、ここでも映像内に表示される場合があります。診断 › テレメトリ取得で解析に役立ちます。", "DJI / Betaflight OSD 由眼镜绘制在自身屏幕上。若将眼镜录制设置为包含 OSD，它也可能出现在这里的视频中。诊断 › 遥测抓取可帮助解析。"),

    # ---- record page
    "rec_folder": ("Recordings folder", "Kayıt klasörü", "Aufnahmeordner", "Carpeta de grabaciones", "Dossier des enregistrements", "Pasta de gravações", "録画フォルダ", "录制文件夹"),
    "rec_change": ("Change…", "Değiştir…", "Ändern…", "Cambiar…", "Modifier…", "Alterar…", "変更…", "更改…"),
    "rec_open": ("Open folder", "Klasörü aç", "Ordner öffnen", "Abrir carpeta", "Ouvrir le dossier", "Abrir pasta", "フォルダを開く", "打开文件夹"),
    "rec_auto": ("Auto-record when video starts", "Görüntü başlayınca otomatik kaydet", "Automatisch aufnehmen, wenn Video startet", "Grabar automáticamente al iniciar el vídeo", "Enregistrer automatiquement au démarrage de la vidéo", "Gravar automaticamente quando o vídeo começar", "映像開始時に自動録画", "视频开始时自动录制"),
    "rec_auto_hint": ("Cleanest recordings: they start exactly at the first keyframe.", "En temiz kayıt: tam ilk keyframe'de başlar.", "Sauberste Aufnahmen: Sie beginnen genau beim ersten Keyframe.", "Las grabaciones más limpias: empiezan justo en el primer keyframe.", "Enregistrements les plus propres : ils commencent pile à la première image clé.", "Gravações mais limpas: começam exatamente no primeiro keyframe.", "最もきれいな録画: 最初のキーフレームから開始します。", "最干净的录制：正好从第一个关键帧开始。"),
    "rec_original": ("Original quality — no re-encoding (always)", "Orijinal kalite, yeniden kodlama yok (her zaman)", "Originalqualität – ohne Neukodierung (immer)", "Calidad original, sin recodificar (siempre)", "Qualité d'origine, sans réencodage (toujours)", "Qualidade original, sem recodificar (sempre)", "オリジナル画質・再エンコードなし（常時）", "原始画质，不重新编码（始终）"),
    "rec_processed": ("Also save processed copy (stabilized, framed)", "İşlenmiş kopyayı da kaydet (stabilize, kadrajlı)", "Auch bearbeitete Kopie speichern (stabilisiert, zugeschnitten)", "Guardar también copia procesada (estabilizada, encuadrada)", "Enregistrer aussi une copie traitée (stabilisée, cadrée)", "Salvar também cópia processada (estabilizada, enquadrada)", "加工版も保存（補正・フレーミング）", "同时保存处理后的副本（防抖、构图）"),
    "rec_replay": ("Instant replay buffer", "Anlık tekrar arabelleği", "Sofort-Replay-Puffer", "Búfer de repetición instantánea", "Tampon de replay instantané", "Buffer de replay instantâneo", "インスタントリプレイ", "即时回放缓存"),
    "rec_replay_keep": ("Keep last {n} s", "Son {n} sn'yi tut", "Letzte {n} s behalten", "Guardar los últimos {n} s", "Garder les {n} dernières s", "Manter os últimos {n} s", "直近{n}秒を保持", "保留最近 {n} 秒"),
    "rec_replay_hint": ("Press B (or Replay) after a great moment to save the last seconds as a clip.", "Güzel bir andan sonra B'ye (veya Tekrar'a) bas, son saniyeler klip olarak kaydedilir.", "Nach einem tollen Moment B (oder Replay) drücken, um die letzten Sekunden als Clip zu speichern.", "Pulsa B (o Repetición) tras un gran momento para guardar los últimos segundos como clip.", "Appuyez sur B (ou Replay) après un beau moment pour sauvegarder les dernières secondes.", "Aperte B (ou Replay) depois de um ótimo momento para salvar os últimos segundos como clipe.", "決定的瞬間の後にB（またはリプレイ）を押すと、直前の数秒をクリップとして保存します。", "精彩瞬间后按 B（或回放），即可将最近几秒保存为片段。"),
    "rec_recent": ("Recent", "Son kayıtlar", "Zuletzt", "Recientes", "Récents", "Recentes", "最近", "最近"),
    "rec_saved": ("Saved: {name}", "Kaydedildi: {name}", "Gespeichert: {name}", "Guardado: {name}", "Enregistré : {name}", "Salvo: {name}", "保存しました: {name}", "已保存：{name}"),
    "rec_saving": ("Saving recording…", "Kayıt kaydediliyor…", "Aufnahme wird gespeichert…", "Guardando grabación…", "Enregistrement en cours de sauvegarde…", "Salvando gravação…", "録画を保存中…", "正在保存录制…"),
    "rec_need_video": ("Video must be running to record.", "Kayıt için önce görüntü gelmeli.", "Zum Aufnehmen muss Video laufen.", "El vídeo debe estar activo para grabar.", "La vidéo doit être active pour enregistrer.", "O vídeo precisa estar ativo para gravar.", "録画するには映像が必要です。", "需有视频才能录制。"),
    "replay_saved": ("Replay saved: {name}", "Tekrar kaydedildi: {name}", "Replay gespeichert: {name}", "Repetición guardada: {name}", "Replay enregistré : {name}", "Replay salvo: {name}", "リプレイを保存しました: {name}", "回放已保存：{name}"),
    "replay_off": ("Turn on the replay buffer first (Record tab).", "Önce tekrar arabelleğini aç (Kayıt sekmesi).", "Zuerst den Replay-Puffer einschalten (Tab „Aufnahme“).", "Activa primero el búfer de repetición (pestaña Grabación).", "Activez d'abord le tampon de replay (onglet Enregistrement).", "Ative primeiro o buffer de replay (aba Gravação).", "先にリプレイを有効にしてください（録画タブ）。", "请先开启回放缓存（录制标签页）。"),
    "snapshot_saved": ("Snapshot saved: {name}", "Fotoğraf kaydedildi: {name}", "Foto gespeichert: {name}", "Captura guardada: {name}", "Capture enregistrée : {name}", "Captura salva: {name}", "スナップショットを保存しました: {name}", "截图已保存：{name}"),

    # ---- diagnostics
    "dg_bitrate": ("Bitrate (Mbit/s)", "Bitrate (Mbit/s)", "Bitrate (Mbit/s)", "Bitrate (Mbit/s)", "Débit (Mbit/s)", "Bitrate (Mbit/s)", "ビットレート (Mbit/s)", "码率 (Mbit/s)"),
    "dg_fps": ("Frame rate (fps)", "Kare hızı (fps)", "Bildrate (fps)", "Fotogramas (fps)", "Images/s (fps)", "Taxa de quadros (fps)", "フレームレート (fps)", "帧率 (fps)"),
    "dg_proc": ("Processing time per frame (ms)", "Kare başına işlem süresi (ms)", "Verarbeitungszeit pro Bild (ms)", "Tiempo de proceso por fotograma (ms)", "Temps de traitement par image (ms)", "Tempo de processamento por quadro (ms)", "1フレームの処理時間 (ms)", "每帧处理时间 (ms)"),
    "dg_device": ("Device", "Cihaz", "Gerät", "Dispositivo", "Appareil", "Dispositivo", "デバイス", "设备"),
    "dg_helper": ("USB helper", "USB yardımcısı", "USB-Helfer", "Asistente USB", "Assistant USB", "Auxiliar USB", "USBヘルパー", "USB 助手"),
    "dg_admin": ("administrator", "yönetici", "Administrator", "administrador", "administrateur", "administrador", "管理者", "管理员"),
    "dg_user": ("user", "kullanıcı", "Benutzer", "usuario", "utilisateur", "usuário", "ユーザー", "用户"),
    "dg_dropped": ("Dropped frames", "Kayıp kareler", "Verlorene Bilder", "Fotogramas perdidos", "Images perdues", "Quadros perdidos", "ドロップフレーム", "丢帧"),
    "dg_packets": ("Packets by type", "Türe göre paketler", "Pakete nach Typ", "Paquetes por tipo", "Paquets par type", "Pacotes por tipo", "種類別パケット", "按类型统计的数据包"),
    "dg_encoder": ("Output encoder", "Çıkış kodlayıcı", "Ausgabe-Encoder", "Codificador de salida", "Encodeur de sortie", "Codificador de saída", "出力エンコーダー", "输出编码器"),
    "dg_none": ("—", "—", "—", "—", "—", "—", "—", "—"),
    "dg_capture": ("Telemetry capture", "Telemetri yakalama", "Telemetrie-Mitschnitt", "Captura de telemetría", "Capture de télémétrie", "Captura de telemetria", "テレメトリ取得", "遥测抓取"),
    "dg_capture_hint": ("Saves the goggles' non-video packets and searches them for readable text, e.g. Betaflight OSD values like “12.4V”.", "Gözlüğün video olmayan paketlerini kaydeder ve içlerinde okunabilir metin arar (ör. “12.4V” gibi Betaflight OSD değerleri).", "Speichert die Nicht-Video-Pakete der Brille und sucht darin lesbaren Text, z. B. Betaflight-OSD-Werte wie „12.4V“.", "Guarda los paquetes no de vídeo de las gafas y busca texto legible, p. ej. valores del OSD de Betaflight como «12.4V».", "Enregistre les paquets non vidéo du casque et y cherche du texte lisible, par ex. des valeurs OSD Betaflight comme « 12.4V ».", "Salva os pacotes não-vídeo dos óculos e procura texto legível, como valores do OSD Betaflight tipo “12.4V”.", "ゴーグルの映像以外のパケットを保存し、「12.4V」のようなBetaflight OSDの値など読める文字列を探します。", "保存眼镜的非视频数据包，并在其中搜索可读文本，例如「12.4V」这类 Betaflight OSD 数值。"),
    "dg_capture_start": ("Start capture", "Yakalamayı başlat", "Mitschnitt starten", "Iniciar captura", "Démarrer la capture", "Iniciar captura", "取得開始", "开始抓取"),
    "dg_capture_stop": ("Stop capture", "Yakalamayı durdur", "Mitschnitt stoppen", "Detener captura", "Arrêter la capture", "Parar captura", "取得停止", "停止抓取"),
    "dg_strings": ("Readable text found", "Bulunan okunabilir metin", "Gefundener lesbarer Text", "Texto legible encontrado", "Texte lisible trouvé", "Texto legível encontrado", "見つかった文字列", "发现的可读文本"),
    "dg_copy": ("Copy report", "Raporu kopyala", "Bericht kopieren", "Copiar informe", "Copier le rapport", "Copiar relatório", "レポートをコピー", "复制报告"),

    # ---- settings
    "set_language": ("Language", "Dil", "Sprache", "Idioma", "Langue", "Idioma", "言語", "语言"),
    "set_web_port": ("Viewer port", "İzleyici portu", "Viewer-Port", "Puerto del visor", "Port de la visionneuse", "Porta do visualizador", "ビューアのポート", "观看端口"),
    "set_ontop": ("Keep window on top", "Pencereyi üstte tut", "Fenster im Vordergrund halten", "Mantener ventana encima", "Garder la fenêtre au premier plan", "Manter janela no topo", "ウィンドウを最前面に表示", "窗口置顶"),
    "set_reset_perm": ("Forget permission choice", "İzin tercihini unut", "Berechtigungswahl vergessen", "Olvidar elección de permisos", "Oublier le choix d'autorisation", "Esquecer escolha de permissão", "権限の選択をリセット", "忘记权限选择"),
    "set_shortcuts": ("Keyboard shortcuts", "Klavye kısayolları", "Tastenkürzel", "Atajos de teclado", "Raccourcis clavier", "Atalhos de teclado", "キーボードショートカット", "键盘快捷键"),
    "set_about": ("About", "Hakkında", "Über", "Acerca de", "À propos", "Sobre", "このアプリについて", "关于"),
    "set_about_text": ("Live view, recording and streaming for DJI Goggles 3 over USB-C. USB protocol notes by the open-source gogglecast project. Not affiliated with or endorsed by DJI.", "DJI Goggles 3 için USB-C üzerinden canlı izleme, kayıt ve yayın. USB protokol bilgileri açık kaynak gogglecast projesinden. DJI ile bağlantısı veya onayı yoktur.", "Live-Ansicht, Aufnahme und Streaming für DJI Goggles 3 über USB-C. USB-Protokollnotizen vom Open-Source-Projekt gogglecast. Nicht mit DJI verbunden oder von DJI unterstützt.", "Vista en directo, grabación y emisión para DJI Goggles 3 por USB-C. Notas del protocolo USB del proyecto de código abierto gogglecast. Sin relación ni respaldo de DJI.", "Vue en direct, enregistrement et diffusion pour DJI Goggles 3 via USB-C. Notes de protocole USB du projet open source gogglecast. Ni affilié ni approuvé par DJI.", "Visualização ao vivo, gravação e transmissão para DJI Goggles 3 via USB-C. Notas do protocolo USB do projeto de código aberto gogglecast. Sem afiliação ou endosso da DJI.", "USB-CによるDJI Goggles 3のライブ表示・録画・配信。USBプロトコル情報はオープンソースのgogglecastプロジェクトによるものです。DJIとは無関係で、DJIの承認を受けていません。", "通过 USB-C 为 DJI Goggles 3 提供实时预览、录制和直播。USB 协议资料来自开源项目 gogglecast。与 DJI 无关，亦未获 DJI 认可。"),
    "sc_rec": ("Record / stop", "Kaydet / durdur", "Aufnahme / Stopp", "Grabar / detener", "Enregistrer / arrêter", "Gravar / parar", "録画 / 停止", "录制 / 停止"),
    "sc_snapshot": ("Snapshot", "Fotoğraf", "Foto", "Captura", "Capture", "Captura", "スナップショット", "截图"),
    "sc_replay": ("Save replay", "Tekrarı kaydet", "Replay speichern", "Guardar repetición", "Enregistrer le replay", "Salvar replay", "リプレイを保存", "保存回放"),
    "sc_full": ("Full screen", "Tam ekran", "Vollbild", "Pantalla completa", "Plein écran", "Tela cheia", "全画面", "全屏"),
    "sc_hide": ("Hide interface (clean view for OBS)", "Arayüzü gizle (OBS için temiz görünüm)", "Oberfläche ausblenden (saubere Ansicht für OBS)", "Ocultar interfaz (vista limpia para OBS)", "Masquer l'interface (vue propre pour OBS)", "Ocultar interface (visão limpa para OBS)", "UIを隠す（OBS用のクリーン表示）", "隐藏界面（供 OBS 使用的纯净画面）"),
    "sc_panel": ("Show / hide panel", "Paneli göster / gizle", "Panel ein-/ausblenden", "Mostrar / ocultar panel", "Afficher / masquer le panneau", "Mostrar / ocultar painel", "パネルの表示 / 非表示", "显示 / 隐藏面板"),
    "sc_esc": ("Exit full screen", "Tam ekrandan çık", "Vollbild beenden", "Salir de pantalla completa", "Quitter le plein écran", "Sair da tela cheia", "全画面を終了", "退出全屏"),
    "web_failed": ("Viewer could not start: {err}", "İzleyici başlatılamadı: {err}", "Viewer konnte nicht starten: {err}", "No se pudo iniciar el visor: {err}", "Impossible de démarrer la visionneuse : {err}", "Não foi possível iniciar o visualizador: {err}", "ビューアを起動できませんでした: {err}", "无法启动观看服务：{err}"),
    "enc_failed": ("Output encoder error: {err}", "Çıkış kodlayıcı hatası: {err}", "Ausgabe-Encoder-Fehler: {err}", "Error del codificador de salida: {err}", "Erreur de l'encodeur de sortie : {err}", "Erro do codificador de saída: {err}", "出力エンコーダーのエラー: {err}", "输出编码器错误：{err}"),
    "on": ("On", "Açık", "An", "Sí", "Activé", "Ligado", "オン", "开"),
    # ---- layout v0.3: info strip, detach
    "btn_detach": ("Detach video", "Videoyu ayır", "Video abdocken", "Separar vídeo", "Détacher la vidéo", "Destacar vídeo", "映像を切り離す", "分离视频"),
    "btn_attach": ("Bring video back", "Videoyu geri al", "Video zurückholen", "Recuperar vídeo", "Rattacher la vidéo", "Trazer vídeo de volta", "映像を戻す", "收回视频"),
    "detached_t": ("Video is in a separate window", "Video ayrı bir pencerede", "Video ist in einem eigenen Fenster", "El vídeo está en otra ventana", "La vidéo est dans une fenêtre séparée", "O vídeo está em uma janela separada", "映像は別ウィンドウに表示中", "视频在单独窗口中"),
    "detached_b": ("Drag it to any monitor; double-click it for full screen. Close it or press D to bring it back.", "İstediğin monitöre sürükle, tam ekran için çift tıkla. Geri almak için kapat ya da D'ye bas.", "Auf einen beliebigen Monitor ziehen, Doppelklick für Vollbild. Schließen oder D drücken, um es zurückzuholen.", "Arrástralo a cualquier monitor; doble clic para pantalla completa. Ciérralo o pulsa D para recuperarlo.", "Faites-la glisser sur n'importe quel écran ; double-clic pour le plein écran. Fermez-la ou appuyez sur D pour la rattacher.", "Arraste para qualquer monitor; clique duas vezes para tela cheia. Feche ou aperte D para trazer de volta.", "好きなモニターへドラッグし、ダブルクリックで全画面にできます。閉じるかDキーで戻ります。", "可拖到任意显示器，双击全屏。关闭窗口或按 D 收回。"),
    "tile_link": ("Link", "Bağlantı", "Verbindung", "Enlace", "Liaison", "Link", "リンク", "链路"),
    "tile_flight": ("Flight", "Uçuş", "Flug", "Vuelo", "Vol", "Voo", "フライト", "飞行"),
    "tile_rec": ("Recording", "Kayıt", "Aufnahme", "Grabando", "Enregistrement", "Gravando", "録画中", "录制中"),
    "tile_live": ("Live", "Yayın", "Live", "En vivo", "Direct", "Ao vivo", "配信", "直播"),
    "tile_clock": ("Clock", "Saat", "Uhr", "Reloj", "Heure", "Relógio", "時刻", "时间"),
    "tile_latency": ("Latency test", "Gecikme testi", "Latenztest", "Prueba de latencia", "Test de latence", "Teste de latência", "遅延テスト", "延迟测试"),
    "set_latency": ("Show latency test clock in the info panel", "Bilgi panelinde gecikme test saatini göster", "Latenz-Testuhr im Infobereich anzeigen", "Mostrar reloj de prueba de latencia en el panel", "Afficher l'horloge de test de latence dans le panneau", "Mostrar relógio de teste de latência no painel", "情報パネルに遅延テスト時計を表示", "在信息面板显示延迟测试时钟"),
    "ov_stream_title": ("Stream overlay", "Yayın overlay'i", "Stream-Overlay", "Superposición de emisión", "Incrustation du flux", "Sobreposição da transmissão", "配信オーバーレイ", "推流叠加层"),
    "ov_stream_hint": ("Burned only into streams, the OBS / browser outputs and processed recordings. The preview always stays clean.", "Sadece yayına, OBS / tarayıcı çıkışlarına ve işlenmiş kayda gömülür. Önizleme her zaman temiz kalır.", "Nur in Streams, OBS-/Browser-Ausgaben und bearbeitete Aufnahmen eingebrannt. Die Vorschau bleibt immer sauber.", "Solo se graba en las emisiones, las salidas de OBS / navegador y las grabaciones procesadas. La vista previa siempre queda limpia.", "Incrusté uniquement dans les flux, les sorties OBS / navigateur et les enregistrements traités. L'aperçu reste toujours propre.", "Gravada só nas transmissões, nas saídas OBS / navegador e nas gravações processadas. A prévia sempre fica limpa.", "配信、OBS／ブラウザ出力、加工済み録画にのみ焼き込まれます。プレビューは常にクリーンです。", "仅烧录到推流、OBS / 浏览器输出和处理后的录制中。预览始终保持干净。"),
    "ov_bf_title": ("Betaflight / DJI OSD", "Betaflight / DJI OSD", "Betaflight-/DJI-OSD", "OSD de Betaflight / DJI", "OSD Betaflight / DJI", "OSD Betaflight / DJI", "Betaflight / DJI OSD", "Betaflight / DJI OSD"),
    "ov_bf_note": ("The goggles draw this OSD into the video pixels themselves, so it is switched on the goggles, not here: turn “Camera View Recording” off on the goggles for a clean feed, on to include the OSD.", "Bu OSD'yi gözlük doğrudan videonun piksellerine çiziyor; bu yüzden buradan değil gözlükten açılıp kapanıyor: temiz görüntü için gözlükte “Camera View Recording”i kapat, OSD'li görüntü için aç.", "Die Brille zeichnet dieses OSD direkt in die Videopixel, daher wird es an der Brille geschaltet, nicht hier: „Camera View Recording“ an der Brille aus = sauberes Bild, an = mit OSD.", "Las gafas dibujan este OSD directamente en los píxeles del vídeo, así que se activa en las gafas, no aquí: desactiva «Camera View Recording» para una imagen limpia y actívalo para incluir el OSD.", "Le casque dessine cet OSD directement dans les pixels de la vidéo ; il se règle donc sur le casque, pas ici : désactivez « Camera View Recording » pour une image propre, activez-le pour inclure l'OSD.", "Os óculos desenham esse OSD direto nos pixels do vídeo, então ele é ligado nos óculos, não aqui: desligue “Camera View Recording” para imagem limpa e ligue para incluir o OSD.", "このOSDはゴーグルが映像のピクセルに直接描き込むため、ここではなくゴーグル側で切り替えます。ゴーグルの「Camera View Recording」をオフでクリーンな映像、オンでOSD付きになります。", "该 OSD 由眼镜直接绘制在视频像素中，因此需在眼镜上切换而非此处：在眼镜上关闭「Camera View Recording」得到干净画面，开启则包含 OSD。"),
    "sc_detach": ("Detach / bring back video", "Videoyu ayır / geri al", "Video abdocken / zurückholen", "Separar / recuperar vídeo", "Détacher / rattacher la vidéo", "Destacar / trazer vídeo", "映像の切り離し / 戻す", "分离 / 收回视频"),

# ---- v0.4
    "pic_mode": ("Mode", "Mod", "Modus", "Modo", "Mode", "Modo", "モード", "模式"),
    "mode_smooth": ("Smooth (≈0.2 s delay)", "Akıcı (≈0,2 sn gecikme)", "Weich (≈0,2 s Verzögerung)", "Suave (≈0,2 s de retardo)", "Fluide (≈0,2 s de délai)", "Suave (≈0,2 s de atraso)", "スムーズ（約0.2秒遅延）", "平滑（约 0.2 秒延迟）"),
    "mode_live": ("Zero delay", "Gecikmesiz", "Ohne Verzögerung", "Sin retardo", "Sans délai", "Sem atraso", "遅延なし", "零延迟"),
    "pic_mode_hint": ("Smooth looks a few frames ahead for the steadiest picture. Only this screen and the outputs wait; your goggles are not affected.", "Akıcı mod en sabit görüntü için birkaç kare ileriye bakar. Sadece bu ekran ve çıkışlar bekler; gözlüğün etkilenmez.", "„Weich“ schaut einige Bilder voraus für das ruhigste Bild. Nur dieser Bildschirm und die Ausgaben warten, die Brille nicht.", "El modo suave mira unos fotogramas por delante para la imagen más estable. Solo esperan esta pantalla y las salidas; tus gafas no se ven afectadas.", "Le mode fluide regarde quelques images en avance pour l'image la plus stable. Seuls cet écran et les sorties attendent ; le casque n'est pas affecté.", "O modo suave olha alguns quadros à frente para a imagem mais estável. Só esta tela e as saídas esperam; seus óculos não são afetados.", "スムーズは数フレーム先を見て最も安定した映像にします。待つのはこの画面と出力だけで、ゴーグルには影響しません。", "平滑模式会预读几帧以获得最稳定的画面。仅此屏幕和输出会等待，眼镜不受影响。"),
    "pic_lens": ("Camera lens (field of view)", "Kamera lensi (görüş açısı)", "Kameraobjektiv (Bildwinkel)", "Lente de la cámara (campo de visión)", "Objectif (champ de vision)", "Lente da câmera (campo de visão)", "カメラレンズ（画角）", "相机镜头（视场角）"),
    "pic_lens_hint": ("Lets the stabilizer undo shake correctly on wide-angle FPV cameras, so the edges don't swim. 150° suits most FPV wide-angle cameras.", "Stabilizasyonun geniş açılı FPV kameralarda sarsıntıyı doğru düzeltmesini sağlar, kenarlar kaymaz. 150° çoğu geniş açılı FPV kamerasına uyar.", "Damit die Stabilisierung Wackler bei Weitwinkel-FPV-Kameras korrekt ausgleicht und die Ränder nicht schwimmen. 150° passt zu den meisten Weitwinkel-FPV-Kameras.", "Permite que el estabilizador corrija bien el temblor en cámaras FPV gran angular, sin que los bordes se deformen. 150° sirve para la mayoría.", "Permet au stabilisateur de corriger correctement les secousses des caméras FPV grand angle, sans que les bords ondulent. 150° convient à la plupart.", "Permite que o estabilizador corrija a trepidação em câmeras FPV grande-angulares sem as bordas ondularem. 150° serve para a maioria.", "広角FPVカメラでも端が揺らがないよう、手ぶれを正しく補正するための設定です。多くの広角FPVカメラには150°が適しています。", "让防抖在广角 FPV 相机上正确消除抖动，边缘不会晃动。150° 适合大多数广角 FPV 相机。"),
    "pic_straighten": ("Straighten lens (remove fisheye)", "Lensi düzelt (balıkgözünü kaldır)", "Objektiv entzerren (Fischauge entfernen)", "Corregir lente (quitar ojo de pez)", "Redresser l'objectif (supprimer le fisheye)", "Corrigir lente (remover olho de peixe)", "レンズ補正（魚眼を除去）", "镜头校正（去除鱼眼）"),
    "aspect_auto": ("Auto", "Otomatik", "Auto", "Auto", "Auto", "Auto", "自動", "自动"),
    "aspect_auto_hint": ("Auto keeps the video's own shape.", "Otomatik, videonun kendi oranını korur.", "„Auto“ behält das Format des Videos bei.", "Auto mantiene la forma original del vídeo.", "Auto conserve le format d'origine de la vidéo.", "Auto mantém o formato original do vídeo.", "「自動」は映像本来の比率を保ちます。", "「自动」保持视频原始比例。"),
    "pic_reset": ("Reset framing", "Kadrajı sıfırla", "Ausschnitt zurücksetzen", "Restablecer encuadre", "Réinitialiser le cadrage", "Redefinir enquadramento", "フレーミングをリセット", "重置构图"),
    "rec_free": ("{gb:.0f} GB free", "{gb:.0f} GB boş", "{gb:.0f} GB frei", "{gb:.0f} GB libres", "{gb:.0f} Go libres", "{gb:.0f} GB livres", "空き {gb:.0f} GB", "可用 {gb:.0f} GB"),
    "tile_stab": ("Stabilizer", "Stabilizasyon", "Stabilisierung", "Estabilizador", "Stabilisation", "Estabilizador", "手ぶれ補正", "防抖"),
    "set_reset_all": ("Reset all settings", "Tüm ayarları sıfırla", "Alle Einstellungen zurücksetzen", "Restablecer todos los ajustes", "Réinitialiser tous les réglages", "Redefinir todos os ajustes", "すべての設定をリセット", "重置所有设置"),
    "set_awake": ("Keep the computer awake while video is live", "Görüntü varken bilgisayarı uyanık tut", "Computer wach halten, solange Video läuft", "Mantener el ordenador despierto con vídeo activo", "Garder l'ordinateur éveillé pendant la vidéo", "Manter o computador acordado com vídeo ativo", "映像受信中はスリープしない", "有视频时保持电脑唤醒"),
}

_cur = ["en"]


def set_language(code):
    _cur[0] = code if code in _ORDER else "en"


def language():
    return _cur[0]


def tr(key, **fmt):
    row = S.get(key)
    if row is None:
        text = key
    else:
        i = _ORDER.index(_cur[0])
        text = row[i] if i < len(row) and row[i] else row[0]
    return text.format(**fmt) if fmt else text


def system_language():
    try:
        from PySide6.QtCore import QLocale
        code = QLocale.system().name().split("_")[0]
        return code if code in _ORDER else "en"
    except Exception:
        return "en"