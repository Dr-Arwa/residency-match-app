import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺")
st.title("Residency Match - Practice Run 🩺")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- THE FIX: Caching and Error Handling ---
try:
    # We change ttl from 0 to 10 seconds to stay under Google's 60-request limit
    interns_df = conn.read(worksheet="Interns", ttl=10)
    specialties_df = conn.read(worksheet="Specialties", ttl=10)
except Exception as e:
    if "429" in str(e):
        st.error("Too many people are clicking at once! Please wait 15 seconds and refresh the page. / ضغط كبير على الموقع، يرجى الانتظار 15 ثانية وإعادة التحميل.")
        st.stop()
    else:
        st.error(f"An error occurred: {e}")
        st.stop()

# Ensure Choices column is treated as text
interns_df['Choices'] = interns_df['Choices'].astype(object)

# --- Authentication Section ---
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
    # --- Main App Logic (If Logged In) ---
    user_name = st.session_state['user_name']
    user_rank = st.session_state['user_rank']
    
    st.write(f"**Welcome:** {user_name} | **Rank:** {user_rank}")
    if st.button("Logout / خروج"):
        st.session_state['logged_in'] = False
        st.rerun()

    # 1. Calculate remaining seats
    available_seats = specialties_df.set_index('Specialty_Name')['Total_Seats'].to_dict()
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
    
    # 3. Handle Choices
    current_choices = interns_df.loc[interns_df['Name'] == user_name, 'Choices'].values[0]
    if pd.notna(current_choices):
        st.info(f"Current saved choices: {current_choices}")

    selected_choices = st.multiselect("Select your preferences in order:", remaining_list)

    if st.button("Save Choices / حفظ الرغبات"):
        if selected_choices:
            try:
                # Fresh read ONLY right before saving to prevent overwriting
                latest_df = conn.read(worksheet="Interns", ttl=0)
                latest_df['Choices'] = latest_df['Choices'].astype(object)
                latest_df.loc[latest_df['Name'] == user_name, 'Choices'] = ",".join(selected_choices)
                
                conn.update(worksheet="Interns", data=latest_df)
                st.success("Saved successfully!")
                # Force the app to clear its memory so everyone sees the change
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error("Server busy. Wait 10 seconds and try 'Save' again.")
        else:
            st.warning("Please select at least one choice.")
