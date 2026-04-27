import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺", layout="wide")
st.title("Residency Match - Live Dashboard 🩺")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- Data Loading with Error Handling ---
try:
    interns_df = conn.read(worksheet="Interns", ttl=10)
    specialties_df = conn.read(worksheet="Specialties", ttl=10)
except Exception as e:
    st.error("Too many people are accessing the system. Please refresh in 15 seconds.")
    st.stop()

interns_df['Choices'] = interns_df['Choices'].astype(object)

# --- Authentication ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.subheader("Login / تسجيل الدخول")
    user_name = st.selectbox("Select your name / اختاري اسمك", interns_df['Name'].dropna().tolist())
    password_input = st.text_input("Enter your Password / أدخلي كلمة المرور", type="password")

    if st.button("Login / دخول"):
        user_row = interns_df[interns_df['Name'] == user_name].iloc[0]
        correct_password = str(user_row['Password']).replace('.0', '').strip()
        if password_input.strip() == correct_password and correct_password != "":
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = user_name
            st.session_state['user_rank'] = int(user_row['Rank'])
            st.rerun()
        else:
            st.error("Incorrect Password.")
else:
    # --- LOGGED IN AREA ---
    user_name = st.session_state['user_name']
    user_rank = st.session_state['user_rank']

    # --- 1. THE SIMULATION ENGINE ---
    # This runs every time the page loads to ensure results are "Live"
    available_seats = specialties_df.set_index('Specialty_Name')['Total_Seats'].to_dict()
    
    # Sort ALL interns who have submitted by rank to simulate the "Turn"
    submitted_interns = interns_df[interns_df['Choices'].notna()].copy()
    submitted_interns = submitted_interns.sort_values('Rank')

    matches = {} # Stores the final result for everyone who submitted

    for _, row in submitted_interns.iterrows():
        choices = str(row['Choices']).split(',')
        assigned = False
        for choice in choices:
            choice = choice.strip()
            if choice in available_seats and available_seats[choice] > 0:
                available_seats[choice] -= 1
                matches[row['Name']] = choice
                assigned = True
                break
        if not assigned:
            matches[row['Name']] = "Unmatched (All choices taken)"

    # --- 2. DISPLAY THE RESULT ---
    st.info(f"Welcome {user_name} | Rank: {user_rank}")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Your Current Status / حالتك الحالية")
        if user_name in matches:
            current_match = matches[user_name]
            st.success(f"### Current Tentative Match: \n # {current_match}")
            st.write("This is based on your rank and the current choices of higher-ranking interns.")
        else:
            st.warning("You haven't submitted your choices yet! / لم تقومي بإدخال رغباتك بعد")

    with col2:
        st.subheader("Available Seats / المقاعد المتاحة")
        remaining_list = [spec for spec, count in available_seats.items() if count > 0]
        for spec in remaining_list:
            st.write(f"- {spec}: ({int(available_seats[spec])} left)")

    st.divider()

    # --- 3. SUBMISSION / UPDATE FORM ---
    st.subheader("Update Your Preferences / تعديل الرغبات")
    st.write("Note: If you have already saved, selecting new ones here and clicking 'Save' will replace your old list.")
    
    selected_choices = st.multiselect(
        "Rank your preferred specialties in order (1st, 2nd, 3rd...):", 
        specialties_df['Specialty_Name'].tolist() # Show ALL specialties so they can pick backups
    )

    if st.button("Save & Update Match / حفظ وتحديث النتيجة"):
        if selected_choices:
            try:
                # Force fresh read before saving to avoid overwriting
                latest_df = conn.read(worksheet="Interns", ttl=0)
                latest_df['Choices'] = latest_df['Choices'].astype(object)
                latest_df.loc[latest_df['Name'] == user_name, 'Choices'] = ",".join(selected_choices)
                
                conn.update(worksheet="Interns", data=latest_df)
                st.success("Preferences updated! Recalculating your match...")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error("Server busy. Please try again in a few seconds.")
        else:
            st.warning("Please select at least one choice.")

    if st.button("Logout / خروج"):
        st.session_state['logged_in'] = False
        st.rerun()
