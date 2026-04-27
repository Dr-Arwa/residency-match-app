import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺")
st.title("Residency Match - Practice Run 🩺")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# CRITICAL FIX 1: ttl=0 ensures we always get the LATEST data, not a cached version
interns_df = conn.read(worksheet="Interns", ttl=0)
specialties_df = conn.read(worksheet="Specialties", ttl=0)

# Ensure Choices column is treated as text even if empty
interns_df['Choices'] = interns_df['Choices'].astype(object)

# --- Authentication Section ---
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
        st.success("Login successful!")
    else:
        st.error("Incorrect Password.")

# --- Main App Logic ---
if st.session_state.get('logged_in'):
    user_name = st.session_state['user_name']
    user_rank = st.session_state['user_rank']
    
    st.write("---")
    st.write(f"**Welcome:** {user_name} | **Rank:** {user_rank}")

    # 1. Calculate remaining seats based on LATEST choices in the sheet
    available_seats = specialties_df.set_index('Specialty_Name')['Total_Seats'].to_dict()
    
    # Get everyone ranked higher who has choices
    higher_ranks = interns_df[(interns_df['Rank'] < user_rank) & (interns_df['Choices'].notna())]
    higher_ranks = higher_ranks.sort_values('Rank')

    for _, row in higher_ranks.iterrows():
        choices = str(row['Choices']).split(',')
        for choice in choices:
            choice = choice.strip()
            if choice in available_seats and available_seats[choice] > 0:
                available_seats[choice] -= 1
                break 

    # 2. Show current availability
    st.subheader("Currently Available Specialties:")
    remaining_list = [spec for spec, count in available_seats.items() if count > 0]
    
    for spec in remaining_list:
        st.write(f"- **{spec}**: {int(available_seats[spec])} seats left")

    st.write("---")
    selected_choices = st.multiselect("Select your preferences in order:", remaining_list)

    # CRITICAL FIX 2: Re-read the entire sheet right before saving to avoid overwriting others
    if st.button("Save Choices / حفظ الرغبات"):
        if selected_choices:
            # Refresh the data one last time before saving
            latest_df = conn.read(worksheet="Interns", ttl=0)
            latest_df['Choices'] = latest_df['Choices'].astype(object)
            
            # Update only the current user's row in the latest data
            latest_df.loc[latest_df['Name'] == user_name, 'Choices'] = ",".join(selected_choices)
            
            # Save the full updated dataframe
            conn.update(worksheet="Interns", data=latest_df)
            st.success("Your choices have been saved securely!")
            st.info("Refresh the page to see the updated standings.")
        else:
            st.warning("Please select at least one choice.")
