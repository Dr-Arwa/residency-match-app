import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺", layout="wide")
st.title("Residency Match - Live Dashboard 🩺")

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

# --- Authentication ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.subheader("Login / تسجيل الدخول")
    user_name = st.selectbox("Select your name", interns_df['Name'].dropna().tolist())
    password_input = st.text_input("Password", type="password")

    if st.button("Login"):
        user_row = interns_df[interns_df['Name'] == user_name].iloc[0]
        correct_password = str(user_row['Password']).replace('.0', '').strip()
        if password_input.strip() == correct_password and correct_password != "":
            st.session_state.update({'logged_in': True, 'user_name': user_name, 'user_rank': int(user_row['Rank'])})
            st.rerun()
        else:
            st.error("Incorrect Password.")
else:
    user_name = st.session_state['user_name']
    user_rank = st.session_state['user_rank']

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
        st.subheader("Available Seats for Your Rank / المتاح لترتيبك")
        # Filter: Only show seats that haven't been taken by HIGHER ranks
        remaining_for_user = [spec for spec, count in user_available_seats.items() if count > 0]
        
        for spec in remaining_for_user:
            st.markdown(
                f'<div dir="rtl" style="text-align: right; font-size: 1.1rem;">'
                f'• **{spec}**: متبقي {int(user_available_seats[spec])} مقعد'
                f'</div>', 
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
