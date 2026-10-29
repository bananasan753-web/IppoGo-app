            if st.button("✨ この目標セットを登録する", type="primary"):
                if lv1 and lv2 and lv3 and lv4 and lv5:
                    new_target = {
                        "title": main_target_input,
                        "tasks": {"Lv.1": lv1, "Lv.2": lv2, "Lv.3": lv3, "Lv.4": lv4, "Lv.5": lv5},
                        "completed": False,
                    }
                    st.session_state.target_list.append(new_target)
                    play_click_sound()
                    st.success(f"📌 目標『{main_target_input}』を登録しました！お菓子画面で選べるようになったよ！")
                    st.rerun()
                else:
                    st.error("⚠️ 全レベルを入力してください。")

        if st.session_state.target_list:
            st.write("---")
            st.markdown("## 🛡️ 登録済みのクエスト一覧")
            for i, target_data in enumerate(st.session_state.target_list):
                with st.expander(f"🎯 {target_data['title']}", expanded=True):

                    # --- 編集モードと通常モードの切り替え ---
                    if st.session_state.get("editing_target_index") == i:
                        st.markdown("### ✏️ 目標の編集")
                        edit_title = st.text_input("最終目標タイトル", value=target_data["title"],
                                                   key=f"edit_title_{i}")
                        edit_lv1 = st.text_input("Lv.1", value=target_data["tasks"].get("Lv.1", ""),
                                                 key=f"edit_lv1_{i}")
                        edit_lv2 = st.text_input("Lv.2", value=target_data["tasks"].get("Lv.2", ""),
                                                 key=f"edit_lv2_{i}")
                        edit_lv3 = st.text_input("Lv.3", value=target_data["tasks"].get("Lv.3", ""),
                                                 key=f"edit_lv3_{i}")
                        edit_lv4 = st.text_input("Lv.4", value=target_data["tasks"].get("Lv.4", ""),
                                                 key=f"edit_lv4_{i}")
                        edit_lv5 = st.text_input("Lv.5", value=target_data["tasks"].get("Lv.5", ""),
                                                 key=f"edit_lv5_{i}")

                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.button("💾 変更を保存", key=f"save_edit_{i}", type="primary",
                                         use_container_width=True):
                                if edit_title and edit_lv1 and edit_lv2 and edit_lv3 and edit_lv4 and edit_lv5:
                                    play_click_sound(delay=0)
                                    target_data["title"] = edit_title.strip()
                                    target_data["tasks"] = {
                                        "Lv.1": edit_lv1, "Lv.2": edit_lv2, "Lv.3": edit_lv3,
                                        "Lv.4": edit_lv4, "Lv.5": edit_lv5
                                    }
                                    st.session_state.editing_target_index = None
                                    st.success("目標を更新しました！")
                                    st.rerun()
                                else:
                                    st.error("⚠️ すべての項目を入力してください。")
                        with cancel_col:
                            if st.button("キャンセル", key=f"cancel_edit_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                st.session_state.editing_target_index = None
                                st.rerun()

                    else:
                        for lv, task in target_data["tasks"].items():
                            st.info(f"**{lv}**: {task}")

                        st.write("")
                        if target_data.get("completed", False):
                            st.success("🎉 この目標は達成済みです！おめでとう！")
                            if st.button("🔄 もう一度挑戦する", key=f"retry_target_{i}"):
                                play_click_sound(delay=0)
                                target_data["completed"] = False
                                st.rerun()
                        else:
                            if st.button("🏆 最終目標を達成した！", type="primary", key=f"complete_target_{i}"):
                                play_achieve_sound(delay=0)
                                target_data["completed"] = True
                                now = get_now_jst()
                                now_datetime_str = now.strftime("%Y/%m/%d %H:%M")
                                today_date_str = now.strftime("%Y/%m/%d")
                                st.session_state.goal_complete_log.append({
                                    "date": now_datetime_str,
                                    "title": target_data["title"],
                                })
                                add_sticker_for_date(today_date_str)
                                st.rerun()

                    st.write("")
                    st.write("---")
                    current_deadline = target_data.get("deadline")
                    if current_deadline:
                        deadline_display = datetime.strptime(current_deadline, "%Y/%m/%d").strftime("%Y年%m月%d日")
                        is_daily_mode = target_data.get("reminder_mode") == "daily"
                        reminder_mode_label = "答えた後も毎日聞く" if is_daily_mode else "その日だけ聞く"

                        if target_data.get("deadline_reminder_stopped"):
                            st.caption(f"🎯 チャレンジ期限：{deadline_display}（リマインドは停止中）")
                        elif is_daily_mode:
                            daily_log = target_data.get("deadline_daily_log", [])
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display}〜（{reminder_mode_label}／これまでの回答数：{len(daily_log)}回）")
                        elif target_data.get("deadline_answered"):
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display}（結果：{target_data.get('deadline_result', '?')} 報告済み）")
                        else:
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display} まで（{reminder_mode_label}／この日になったら結果を聞くよ）")

                        if st.button("期限を解除する", key=f"clear_deadline_{i}"):
                            play_click_sound(delay=0)
                            target_data["deadline"] = None
                            target_data["deadline_answered"] = False
                            target_data["deadline_result"] = None
                            target_data["reminder_mode"] = "once"
                            target_data["deadline_reminder_stopped"] = False
                            target_data["deadline_daily_log"] = []
                            st.rerun()
                    else:
                        with st.expander("🎯 この日までチャレンジ！を設定する"):
                            new_deadline = st.date_input("いつまでに頑張る？", value=get_now_jst().date(),
                                                         key=f"deadline_input_{i}")
                            new_reminder_mode = st.radio(
                                "結果はいつ聞く？",
                                options=["once", "daily"],
                                format_func=lambda
                                    m: "その日だけ聞く" if m == "once" else "答えた後も毎日聞く（繰り返しチェックイン）",
                                key=f"deadline_mode_{i}",
                            )
                            if st.button("この日を設定する", key=f"set_deadline_{i}"):
                                play_click_sound(delay=0)
                                target_data["deadline"] = new_deadline.strftime("%Y/%m/%d")
                                target_data["deadline_answered"] = False
                                target_data["deadline_result"] = None
                                target_data["reminder_mode"] = new_reminder_mode
                                target_data["deadline_reminder_stopped"] = False
                                target_data["deadline_daily_log"] = []
                                st.rerun()

                    st.write("---")
                    # 操作ボタンエリア（編集・複製・削除）
                    if st.session_state.get("confirm_delete_target_index") == i:
                        st.warning(f"『{target_data['title']}』を削除しますか？この操作は取り消せません。")
                        del_confirm_col, del_cancel_col = st.columns(2)
                        with del_confirm_col:
                            if st.button("🗑️ 削除する", key=f"confirm_delete_target_yes_{i}"):
                                play_click_sound(delay=0)
                                st.session_state.target_list.pop(i)
                                st.session_state.confirm_delete_target_index = None
                                st.rerun()
                        with del_cancel_col:
                            if st.button("やめる", key=f"confirm_delete_target_no_{i}"):
                                play_click_sound(delay=0)
                                st.session_state.confirm_delete_target_index = None
                                st.rerun()
                    else:
                        col_edit, col_copy, col_del = st.columns(3)
                        with col_edit:
                            if st.button("✏️ 編集", key=f"edit_target_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                st.session_state.editing_target_index = i
                                st.rerun()
                        with col_copy:
                            if st.button("📋 複製", key=f"copy_target_{i}", use_container_width=True):
                                play_click_sound(delay=0)
