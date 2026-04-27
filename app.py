import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺", layout="wide")
st.title("Residency Match - Live Dashboard 🩺")
total_submitted = interns_df['Choices'].notna().sum()
st.caption(f"Progress: {total_submitted} / 142 interns have submitted their preferences.")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- Data Loading (142 Interns, 106 Seats) ---
try:
    # Use 10s TTL to prevent 429 Errors
    interns_df = conn.read(worksheet="Interns", ttl=10)
    specialties_df = conn.read(worksheet="Specialties", ttl=10)
except Exception as e:
    st.error("Too many people are accessing the system. Please refresh in 15 seconds.")
    st.stop()

# Ensure Choices column is text
interns_df['Choices'] = interns_df['Choices'].astype(object)

# --- Authentication Section ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.subheader("Login")
    
    # 1. Create a list of RANKS instead of NAMES
    rank_options = []
    rank_to_data = {} # Bridge to link the label back to the full row

    for _, row in interns_df.iterrows():
        rank_num = int(row['Rank'])
        name = str(row['Name'])
        has_submitted = pd.notna(row['Choices']) and str(row['Choices']).strip() != ""
        symbol = "✅" if has_submitted else "⏳"
        
        # Display as "Rank 1 ✅" or "الترتيب ١ ✅"
        label = f"Rank {rank_num} | الترتيب {rank_num} {symbol}"
        rank_options.append(label)
        
        # Store the real name and rank behind this label
        rank_to_data[label] = {"name": name, "rank": rank_num}

    # 2. Dropdown now shows Ranks
    selected_label = st.selectbox("Select your Rank / اختاري ترتيبك", rank_options)
    user_info = rank_to_data[selected_label]
    
    password_input = st.text_input("Enter your Password / أدخلي كلمة المرور", type="password")

    if st.button("Login / دخول"):
        # Fetch the row based on the hidden name/rank
        user_row = interns_df[interns_df['Name'] == user_info['name']].iloc[0]
        correct_password = str(user_row['Password']).replace('.0', '').strip()
        
        if password_input.strip() == correct_password and correct_password != "":
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = user_info['name']
            st.session_state['user_rank'] = user_info['rank']
            st.rerun()
        else:
            st.error("Incorrect Password. / كلمة المرور غير صحيحة")

    # --- THE FIXED SIMULATION ENGINE ---
    # Start with a fresh count of ALL seats
    full_inventory = specialties_df.set_index('Specialty_Name')['Total_Seats'].to_dict()
    
    # Get all submitted data and sort strictly by Rank
    all_submissions = interns_df[interns_df['Choices'].notna()].copy()
    all_submissions = all_submissions.sort_values('Rank')

    # This will hold the "Final Match" for everyone
    matches = {}
    # This will hold the seats available specifically for YOU
    user_available_seats = full_inventory.copy()

    for _, row in all_submissions.iterrows():
        choices = str(row['Choices']).split(',')
        assigned_specialty = "Unmatched"
        
        for choice in choices:
            choice = choice.strip()
            # If the specialty has seats left in the "Full Inventory"
            if choice in full_inventory and full_inventory[choice] > 0:
                # If this intern is HIGHER ranked than you, they consume a seat from your view
                if int(row['Rank']) < user_rank:
                    user_available_seats[choice] -= 1
                
                # They consume the seat from the global match
                full_inventory[choice] -= 1
                assigned_specialty = choice
                break
        
        matches[row['Name']] = assigned_specialty

    # --- DISPLAY ---
    st.info(f"Welcome {user_name} | Rank: {user_rank}")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Your Current Status / حالتك الحالية")
        if user_name in matches:
            # Using HTML to ensure the box and text align correctly for Arabic
            st.markdown(
                f'<div dir="rtl" style="text-align: right; background-color: #1e3d33; padding: 20px; border-radius: 10px; border: 1px solid #2e7d32;">'
                f'<span style="font-size: 1.2rem;">التخصص المرشح لكِ حالياً هو:</span><br>'
                f'<span style="font-size: 2rem; font-weight: bold; color: #4caf50;">{matches[user_name]}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
        else:
            st.warning("لم تقومي بإدخال رغباتك بعد!")

    with col2:
        st.subheader("المقاعد المتاحة لترتيبك")
        remaining_for_user = [spec for spec, count in user_available_seats.items() if count > 0]
        
        for spec in remaining_for_user:
            # Clean HTML without ** symbols
            # Added a light border-bottom for better visual separation
            st.markdown(
                f'''
                <div dir="rtl" style="
                    text-align: right; 
                    font-size: 1.15rem; 
                    padding: 8px 0; 
                    border-bottom: 1px solid #3d3d3d; 
                    font-weight: 500;
                    color: #e0e0e0;
                ">
                    • {spec}: متبقي {int(user_available_seats[spec])} مقعد
                </div>
                ''', 
                unsafe_allow_html=True
            )



    st.divider()

    # --- SUBMISSION ---
    st.subheader("Update Your Preferences")
    selected_choices = st.multiselect("Rank your preferences (Only available seats shown):", remaining_for_user)

    if st.button("Save & Update"):
        if selected_choices:
            try:
                latest_df = conn.read(worksheet="Interns", ttl=0)
                latest_df['Choices'] = latest_df['Choices'].astype(object)
                latest_df.loc[latest_df['Name'] == user_name, 'Choices'] = ",".join(selected_choices)
                conn.update(worksheet="Interns", data=latest_df)
                st.success("Updated! Recalculating...")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception:
                st.error("Server busy. Try again in 10 seconds.")
        else:
            st.warning("Select at least one choice.")

    if st.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
