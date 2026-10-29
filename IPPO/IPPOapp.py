                    st.caption(f"持っている数：{st.session_state.dino_food.get(food_key, 0)}個")
                    if st.button("購入する", key=f"dino_buy_{food_key}", use_container_width=True):
                        if st.session_state.aqua_points >= food["price"]:
                            st.session_state.aqua_points -= food["price"]
                            st.session_state.dino_food[food_key] = st.session_state.dino_food.get(food_key, 0) + 1
                            save_progress()
                            st.success(f"{food['emoji']} {food['name']}を買いました！")
                            st.rerun()
                        else:
                            st.warning("ポイントが足りません！")

            st.write("---")
            st.markdown("#### 🌟 スペシャルダイス")
            st.write("**スペシャルダイス** — 5ポイント ／ 1回だけ、1〜6から好きな目を選べます。")
            st.caption(f"所持数：{int(st.session_state.get('dino_special_dice', 0))}個")
            if st.button("🌟 スペシャルダイスを購入（5ポイント）", key="dino_buy_special_dice", use_container_width=True):
                if st.session_state.aqua_points >= 5:
                    st.session_state.aqua_points -= 5
                    st.session_state.dino_special_dice = int(st.session_state.get("dino_special_dice", 0)) + 1
                    save_progress()
                    st.success("スペシャルダイスを1個購入しました！レースで好きな目を選んで使えます。")
                    st.rerun()
                else:
                    st.warning("ポイントが足りません！")

            st.write("---")
            st.markdown("#### 🏁 コースショップ")
            st.caption("ポイントで新しいすごろくコースを解放できます。")
            for course_key in ("survival", "relax"):
                course_data = DINO_COURSES[course_key]
                owned_course = course_key in st.session_state.get("dino_unlocked_courses", [])
                st.markdown(f"**{('🏆' if course_key == 'survival' else '🌸')} {course_data['name']}** — {course_data['price']}ポイント")
                st.caption("バトルマスがたくさん！手ごわいサバイバル。" if course_key == "survival" else "和むイベントマスがたくさんある、のんびりコース。")
                if owned_course:
                    st.success("購入済み")
                elif st.button(f"購入する（{course_data['price']}ポイント）", key=f"dino_course_buy_{course_key}", use_container_width=True):
                    if st.session_state.aqua_points >= course_data["price"]:
                        st.session_state.aqua_points -= course_data["price"]
                        st.session_state.setdefault("dino_unlocked_courses", []).append(course_key)
                        save_progress()
                        st.success(f"{course_data['name']}を解放しました！")
                        st.rerun()
                    else:
                        st.warning("ポイントが足りません！")

            st.write("---")
            st.markdown("#### 🧪 能力アップアイテム")
            stat_target_idx = st.selectbox(
                "能力を上げる恐竜", list(range(len(st.session_state.dino_owned))),
                format_func=lambda i: f"{DINO_SPECIES[st.session_state.dino_owned[i]['species']]['emoji']} {dino_display_name(st.session_state.dino_owned[i])}",
                key="dino_stat_target",
            )
            for item in DINO_SHOP_DATA["stat_items"]:
                st.markdown(f"**{item['emoji']} {item['name']}** — {item['price']}ポイント ／ 経験値 +{item['exp']} ／ 能力 +{item['amount']}")
                if st.button(f"{item['name']}を購入して使う", key=f"dino_stat_buy_{item['id']}", use_container_width=True):
                    if st.session_state.aqua_points >= item["price"]:
                        st.session_state.aqua_points -= item["price"]
                        target = st.session_state.dino_owned[stat_target_idx]
                        stat_key = {"hp":"hp_bonus", "attack":"attack_bonus", "speed":"speed_bonus"}[item["stat"]]
                        target[stat_key] = int(target.get(stat_key, 0)) + item["amount"]
                        record_dino_growth(target, f"{item['emoji']} {item['name']}を使った！ {DINO_GROWTH_STATS[item['stat']]['label']} +{item['amount']}")
                        add_dino_exp(target, item["exp"])
                        add_dino_message(f"{item['emoji']} {dino_display_name(target)}に{item['name']}を使った！ 経験値 +{item['exp']}、{item['stat']} +{item['amount']}！")
                        save_progress()
                        st.rerun()
                    else:
                        st.warning("ポイントが足りません！")

            st.write("---")
            st.markdown("#### 🍇 木の実を食べる")
            st.caption("力試しの勝利でもらった木の実を食べると、対応する能力が上がるよ！")
            berry_target_idx = st.selectbox(
                "木の実を食べる恐竜", list(range(len(st.session_state.dino_owned))),
                format_func=lambda i: f"{DINO_SPECIES[st.session_state.dino_owned[i]['species']]['emoji']} {dino_display_name(st.session_state.dino_owned[i])}（Lv.{dino_level(st.session_state.dino_owned[i])}）",
                key="dino_berry_target",
            )
            for berry_key, berry in DINO_BERRIES.items():
                stock = st.session_state.get("dino_berries", {}).get(berry_key, 0)
                amount = 2 if berry_key.endswith("_plus") else 1
                if st.button(f"{berry['emoji']} {berry['name']}（残り{stock}個・{berry['label']}+{amount}）を食べる",
                             disabled=stock <= 0, key=f"dino_berry_eat_{berry_key}", use_container_width=True):
                    eat_dino_berry(st.session_state.dino_owned[berry_target_idx], berry_key)
                    st.rerun()

            st.write("---")
            st.markdown("#### 🍽️ 餌をあげる")
            owned_dinos = st.session_state.dino_owned
            feed_index = st.selectbox(
                "どの恐竜にあげる？", list(range(len(owned_dinos))),
                format_func=lambda i: f"{DINO_SPECIES[owned_dinos[i]['species']]['emoji']} {dino_display_name(owned_dinos[i])}（Lv.{dino_level(owned_dinos[i])}）",
                key="dino_feed_target",
            )
            for food_key, food in DINO_FOOD.items():
                stock = st.session_state.dino_food.get(food_key, 0)
                if st.button(f"{food['emoji']} {food['name']}をあげる（残り{stock}個・経験値+{food['exp']}）",
                             disabled=stock <= 0, key=f"dino_feed_{food_key}", use_container_width=True):
                    target = owned_dinos[feed_index]
                    st.session_state.dino_food[food_key] -= 1
                    add_dino_message(f"{food['emoji']} {dino_display_name(target)}は{food['name']}をもぐもぐ！ 経験値 +{food['exp']}")
                    queue_dino_sound("feed")
                    add_dino_exp(target, food["exp"])
                    save_progress()
                    st.rerun()


# =====================================================
# 💾 Supabase への自動セーブ
# =====================================================
if st.session_state.get("game_started"):
    save_progress()
