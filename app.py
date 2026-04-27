import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Residency Match Practice", page_icon="🩺")
st.title("Residency Match - Practice Run 🩺")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
interns_df = conn.read(worksheet="Interns")
specialties_df = conn.read(worksheet="Specialties")

# --- to make the python understand that the specialties could be words not numbers ---

interns_df['Choices'] = interns_df['Choices'].astype(object)

# --- Authentication Section ---
st.subheader("Login / تسجيل الدخول")

# Select Name and Enter Password
user_name = st.selectbox("Select your name / اختاري اسمك", interns_df['Name'].dropna().tolist())
password_input = st.text_input("Enter your Password / أدخلي كلمة المرور", type="password")

if st.button("Login / دخول"):
    # Find the user's row
    user_row = interns_df[interns_df['Name'] == user_name].iloc[0]
    
    # Check if password matches (ignoring extra spaces)
    correct_password = str(user_row['Password']).strip()
    
    if password_input.strip() == correct_password:
        st.session_state['logged_in'] = True
        st.session_state['user_name'] = user_name
        st.session_state['user_rank'] = int(user_row['Rank'])
        st.success("Login successful!")
    else:
        st.error("Incorrect Password. Please try again. / كلمة المرور غير صحيحة")
        st.session_state['logged_in'] = False

# --- Main App Logic (Only shows if logged in) ---
if st.session_state.get('logged_in'):
    user_name = st.session_state['user_name']
    user_rank = st.session_state['user_rank']
    
    st.write("---")
    st.write(f"**Welcome / أهلاً بكِ:** {user_name}")
    st.write(f"**Your Official Rank / الترتيب:** {user_rank}")

    # 1. Calculate remaining seats based on HIGHER ranks
    available_seats = specialties_df.set_index('Specialty_Name')['Total_Seats'].to_dict()
    
    # Get all interns ranked higher than the current user who have made choices
    higher_ranks = interns_df[(interns_df['Rank'] < user_rank) & (interns_df['Choices'].notna())]
    higher_ranks = higher_ranks.sort_values('Rank')

    # Subtract seats taken by higher ranks
    for _, row in higher_ranks.iterrows():
        choices = str(row['Choices']).split(',')
        for choice in choices:
            choice = choice.strip()
            if choice in available_seats and available_seats[choice] > 0:
                available_seats[choice] -= 1
                break # Move to next intern once they secure a seat

    # 2. Show what is currently left
    st.subheader("Currently Available Specialties for You / التخصصات المتاحة لكِ حالياً:")
    remaining_list = [spec for spec, count in available_seats.items() if count > 0]
    
    if not remaining_list:
        st.warning("All seats have been taken by higher ranks.")
    else:
        for spec in remaining_list:
            st.write(f"- **{spec}**: {int(available_seats[spec])} seats left")

        st.write("---")
        st.subheader("Submit Your Preferences / اختاري رغباتك بالترتيب")
        
        # Show previous choices if they exist
        current_choices_str = interns_df.loc[interns_df['Name'] == user_name, 'Choices'].values[0]
        if pd.notna(current_choices_str) and str(current_choices_str).strip() != "":
            st.info(f"Your current saved choices: {current_choices_str}")

        # The Selection Tool
        selected_choices = st.multiselect(
            "Select your preferences in order (Pick as many as you want):", 
            remaining_list
        )

        # 3. Save choices back to database
        if st.button("Save Choices / حفظ الرغبات"):
            if selected_choices:
                # Join the list into a comma-separated string
                interns_df.loc[interns_df['Name'] == user_name, 'Choices'] = ",".join(selected_choices)
                
                # Write back to Google Sheets
                conn.update(worksheet="Interns", data=interns_df)
                st.success("Your choices have been saved securely! / تم الحفظ بنجاح")
            else:
                st.warning("Please select at least one choice. / يرجى اختيار رغبة واحدة على الأقل")
