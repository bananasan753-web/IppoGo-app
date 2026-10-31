            elif level == tank["level"] + 1:
                remaining = max(0, level_data["required"] - tank_score)
                st.info(f"🔓 次の水槽 **Lv.{level} {level_data['name']}**：豪華度 {level_data['required']} 必要（あと {remaining}）")
        if tank["level"] == AQUA_TANK_LEVELS[-1]["level"]:
            st.success("🏆 最高レベルに到達！")

    # --- 恐竜レースページ ---
    elif st.session_state.page == "dino_page":
        st.title("🦖 恐竜レース")
        ensure_dino_data()
        partner = get_dino_partner()

        # 効果音・演出は、画面更新後に一度だけ
        dino_sound_kind = st.session_state.pop("dino_sound", None)
        if dino_sound_kind == "finish":
            play_jar_full_sound(delay=0)
            st.balloons()
        elif dino_sound_kind == "achieve":
            play_achieve_sound(delay=0)
        elif dino_sound_kind == "points":
            play_aqua_point_sound(delay=0)
        elif dino_sound_kind == "feed":
            play_aqua_feed_sound(delay=0)
        elif dino_sound_kind == "click":
            play_click_sound(delay=0)

        st.caption("サイコロで進むすごろくレース！ 1マス＝100m。戻るマスはないので、安心して進もう🦖")

        # ポイント・パートナー表示
        info1, info2, info3 = st.columns(3)
        with info1:
            st.metric("💎 IPPOポイント", st.session_state.ippo_points)
        with info2:
            if partner:
                st.metric("🤝 パートナー", f"{DINO_SPECIES[partner['species']]['emoji']} {dino_display_name(partner)}")
            else:
                st.metric("🤝 パートナー", "未選択")
        with info3:
            st.metric("🎲 サイコロ1回", f"{DINO_DICE_COST} IPPOポイント")

        # 目標を達成して共通のIPPOポイントをゲット
        with st.expander("🏆 目標を達成してIPPOポイントをゲット！"):
            st.caption("達成した目標のレベルぶんだけIPPOポイントがもらえます。")
            if not st.session_state.target_list:
                st.warning("⚠️ まだ目標が登録されていません！『目標登録』で目標を作ってね！")
            else:
                dino_target_titles = [t["title"] for t in st.session_state.target_list]
                dino_target_title = st.selectbox("🎯 どの目標を達成した？", dino_target_titles, key="dino_target_select")
                dino_target_data = next(t for t in st.session_state.target_list if t["title"] == dino_target_title)
                dino_level_options = [
                    f"{lv}: {task} (💎{int(lv.replace('Lv.', '').replace('Lv', ''))} IPPOポイント)"
                    for lv, task in dino_target_data["tasks"].items()
                ]
                dino_level_str = st.selectbox("⭐ どのレベルをクリアした？", dino_level_options, key="dino_level_select")
                dino_lv_key = dino_level_str.split(":")[0]
                dino_task_text = dino_target_data["tasks"][dino_lv_key]
                if st.button("➕ この1歩を達成した！", type="primary", key="dino_achieve_button"):
                    dino_earned = int(dino_lv_key.replace("Lv.", "").replace("Lv", ""))
                    st.session_state.ippo_points += dino_earned
                    st.session_state.aqua_goal_log.append({
                        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                        "target": dino_target_title, "level": dino_lv_key, "task": dino_task_text,
                        "points": dino_earned, "source": "dino",
                    })
                    add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
                    queue_dino_sound("points")
                    add_dino_message(f"🎉 目標達成！ {dino_earned} IPPOポイントをゲットしたよ！")
                    save_progress()
                    st.rerun()

        # 直前の出来事（サイコロの結果など）
        dino_messages = st.session_state.pop("dino_messages", [])
        if dino_messages:
            with st.container(border=True):
                for message_text in dino_messages:
                    st.write(message_text)

        race_tab, dino_tab, dino_shop_tab = st.tabs(["🏁 レース", "🦖 恐竜たち", "🍖 恐竜ショップ"])

        # ---------------- レース ----------------
        with race_tab:
            course_keys = ["beginner", "intermediate", "advanced"] + [
                k for k in ("survival", "relax")
                if k in st.session_state.get("dino_unlocked_courses", [])
            ]
            course_key = st.selectbox(
                "🗺️ コースを選ぶ", course_keys,
                format_func=lambda k: f"{DINO_COURSES[k]['tier']} {DINO_COURSES[k]['name']}（{DINO_COURSES[k]['distance_km']}km）",
                key="dino_course_choice",
            )
            course = DINO_COURSES[course_key]
            if not course["ready"]:
                st.info(f"🚧 {course['tier']} {course['name']} は現在準備中です！お楽しみに！")
            elif partner is None:
                st.warning("🤝 まずは『恐竜たち』タブで、一緒に走るパートナーを選んでね！")
            else:
                race = get_dino_race(course_key)
                goal = dino_course_goal(course_key)
                partner_species = DINO_SPECIES[partner["species"]]
                partner_level = dino_level(partner)
                st.markdown(f"#### {partner_species['emoji']} {dino_display_name(partner)}（Lv.{partner_level}）と一緒に走ろう！")
                st.write(f"📍 現在地：**{race['pos'] * 100}m / {goal * 100}m**（{race['pos']}/{goal}マス）　🏁 完走 {race['laps']}回")
                st.progress(min(race["pos"] / goal, 1.0))
                st.markdown(render_dino_board(course_key, race["pos"], partner_species["emoji"]), unsafe_allow_html=True)
                st.caption("💨 追い風　🎲 もう一回　🍖 食べ物　⚔️ バトル（力試し・挑むかは自由）　🏁 ゴール")
                st.write("")

                # 模型恐竜との練習はレース進行に関係なくいつでも開始できる
                if st.session_state.get("dino_battle") is None and st.button(
                    "🧸 模型の恐竜と練習バトル（いつでも挑戦・報酬なし）",
                    use_container_width=True, key="dino_practice_battle"):
                    start_dino_practice_battle(partner)
                    st.rerun()

                battle = st.session_state.get("dino_battle")
                if battle:
                    # ===== バトル中 =====
                    enemy = battle["enemy"]
                    st.markdown(f"### ⚔️ 力試し！ vs {enemy['emoji']} {enemy['name']}（Lv.{enemy['level']}）")
                    col_me, col_enemy = st.columns(2)
                    with col_me:
                        st.markdown(f"**{partner_species['emoji']} {dino_display_name(partner)}**")
                        st.caption(f"HP {battle['player_hp']} / {battle['player_max_hp']}")
                        st.progress(battle["player_hp"] / battle["player_max_hp"])
                    with col_enemy:
                        st.markdown(f"**{enemy['emoji']} {enemy['name']}**")
                        st.caption(f"HP {battle['enemy_hp']} / {enemy['max_hp']}")
                        st.progress(battle["enemy_hp"] / enemy["max_hp"])
                    with st.container(border=True):
                        for line in battle["log"]:
                            st.write(line)

                    if battle["over"]:
                        end_label = "🧸 練習を終える" if battle.get("practice") else "🏁 レースにもどる"
                        if st.button(end_label, type="primary", use_container_width=True, key="dino_battle_end"):
                            del st.session_state["dino_battle"]
                            st.rerun()
                    else:
                        special_left = battle.get("special_left", 0)
                        st.caption(f"🌟 固有技『{partner_species['special_name']}』：{partner_species['special_text']}（この力試しであと {special_left}回）")
                        battle_actions = [
                            ("attack", "⚔️ こうげき"), ("defend", "🛡️ ぼうぎょ"),
                            ("special", f"🌟 固有技({special_left})"), ("flee", "🏃 にげる"),
                        ]
                        for action_col, (action_key, action_label) in zip(st.columns(4), battle_actions):
                            with action_col:
                                if st.button(action_label, use_container_width=True, key=f"dino_battle_{action_key}",
                                             disabled=(action_key == "special" and special_left <= 0)):
                                    resolve_dino_battle_turn(partner, action_key)
                                    st.rerun()
                        with st.expander("📖 戦い方のルール"):
                            st.write("⚔️ **こうげき**：1〜5のダメージ。ただし相手がぼうぎょだと反撃される！")
                            st.write("🛡️ **ぼうぎょ**：相手がこうげきなら攻撃を止めて大きな反撃！ でも相手が固有技・強打のときは防げない。")
                            st.write(f"🌟 **固有技**：恐竜ごとの特別な技。ぼうぎょされても止められない。1回の力試しで{DINO_SPECIAL_USES}回まで。")
                            st.write("🏃 **にげる**：いつでも安全に逃げられる。")

                elif race["pending_battle"]:
                    # ===== バトルマスに到着（挑むかどうかは自由）=====
                    pending = race["pending_battle"]
                    st.warning(f"⚔️ 野良の {pending['emoji']} {pending['name']}（Lv.{pending['level']}）があらわれた！ 力試しに挑戦する？")
