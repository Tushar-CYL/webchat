import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import time
import hashlib

# MongoDB connection
client = MongoClient("mongodb+srv://tusharkanti:993355%40Tushar@cluster0.w5gny.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client.chat_database
users_collection = db.users
chats_collection = db.chats

class RealTimeChatApp:
    def __init__(self):
        self.initialize_session_state()

    def initialize_session_state(self):
        if "user_id" not in st.session_state:
            st.session_state.user_id = None
        if "username" not in st.session_state:
            st.session_state.username = None
        if "current_chat" not in st.session_state:
            st.session_state.current_chat = None
        if "last_message_time" not in st.session_state:
            st.session_state.last_message_time = datetime.now()
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "sending_message" not in st.session_state:
            st.session_state.sending_message = False

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password):
        try:
            if users_collection.find_one({"username": username}):
                return False, "Username already exists"

            user_data = {
                'username': username,
                'password': self.hash_password(password),
                'created_at': str(datetime.now()),
                'last_seen': str(datetime.now()),
                'online': True
            }
            users_collection.insert_one(user_data)
            return True, "Registration successful"
        except Exception as e:
            return False, str(e)

    def login_user(self, username, password):
        try:
            user_data = users_collection.find_one({"username": username})

            if user_data and user_data['password'] == self.hash_password(password):
                st.session_state.user_id = username
                st.session_state.username = username
                users_collection.update_one(
                    {"username": username},
                    {"$set": {
                        'online': True,
                        'last_seen': str(datetime.now())
                    }}
                )
                return True, "Login successful"
            return False, "Invalid credentials"
        except Exception as e:
            return False, str(e)

    def send_message(self, receiver, message):
        try:
            st.session_state.sending_message = True
            chat_id = self.get_chat_id(st.session_state.username, receiver)
            message_data = {
                'sender': st.session_state.username,
                'receiver': receiver,
                'content': message,
                'timestamp': str(datetime.now()),
                'read': False
            }

            # Insert the message into the appropriate chat document
            chat = chats_collection.find_one({"chat_id": chat_id})
            if chat:
                chats_collection.update_one(
                    {"chat_id": chat_id},
                    {"$push": {"messages": message_data}}
                )
            else:
                chats_collection.insert_one({
                    "chat_id": chat_id,
                    "messages": [message_data]
                })

            st.session_state.last_message_time = datetime.now()
            st.info("Message sent successfully!")
            st.session_state.sending_message = False
            return True
        except Exception as e:
            st.error(f"Error sending message: {str(e)}")
            st.session_state.sending_message = False
            return False

    def get_chat_id(self, user1, user2):
        users = sorted([user1, user2])
        return f"{users[0]}_{users[1]}"

    def get_messages(self, other_user):
        chat_id = self.get_chat_id(st.session_state.username, other_user)
        chat_data = chats_collection.find_one({"chat_id": chat_id})

        if chat_data and "messages" in chat_data:
            sorted_messages = sorted(
                chat_data["messages"],
                key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
            )
            return sorted_messages
        return []

    def get_contacts(self):
        users = users_collection.find()
        contacts = []
        for user in users:
            if user['username'] != st.session_state.username:
                contacts.append({
                    'username': user['username'],
                    'online': user.get('online', False),
                    'last_seen': user.get('last_seen', '')
                })
        return contacts

    def mark_messages_as_read(self, other_user):
        chat_id = self.get_chat_id(st.session_state.username, other_user)
        
        # Update all unread messages where the current user is the receiver
        chats_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "messages.$[elem].read": True
            }},
            array_filters=[{
                "elem.receiver": st.session_state.username,
                "elem.read": False
            }]
        )

    def update_online_status(self):
        if st.session_state.username:
            users_collection.update_one(
                {"username": st.session_state.username},
                {"$set": {
                    'last_seen': str(datetime.now()),
                    'online': True
                }}
            )

    def render_message(self, message):
        is_sender = message['sender'] == st.session_state.username

        col1, col2 = st.columns([0.85, 0.15]) if is_sender else st.columns([0.15, 0.85])

        with col1:
            if not is_sender:
                st.chat_message("assistant").write(message['content'])
            else:
                st.chat_message("user").write(message['content'])

        with col2:
            if is_sender:
                timestamp = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
                st.caption(timestamp.strftime('%H:%M'))
                if message.get('read', False):
                    st.caption("✓✓")
                else:
                    st.caption("✓")

    def render_chat_interface(self):
        st.title("💬 Real-time Chat")

        with st.sidebar:
            st.subheader(f"Welcome, {st.session_state.username}!")
            if st.button("Logout"):
                if st.session_state.username:
                    users_collection.update_one(
                        {"username": st.session_state.username},
                        {"$set": {
                            'online': False,
                            'last_seen': str(datetime.now())
                        }}
                    )
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.rerun()

            st.subheader("Contacts")
            contacts = self.get_contacts()
            for contact in contacts:
                col1, col2 = st.columns([0.7, 0.3])
                with col1:
                    if st.button(f"💬 {contact['username']}", key=contact['username']):
                        st.session_state.current_chat = contact['username']
                        st.rerun()
                with col2:
                    if contact['online']:
                        st.success("Online")
                    else:
                        st.caption("Offline")

        if st.session_state.current_chat:
            st.subheader(f"Chat with {st.session_state.current_chat}")

            messages_container = st.container()
            with messages_container:
                messages = self.get_messages(st.session_state.current_chat)
                for message in messages:
                    self.render_message(message)

                self.mark_messages_as_read(st.session_state.current_chat)

            message = st.chat_input("Type your message...")
            if message:
                if self.send_message(st.session_state.current_chat, message):
                    time.sleep(0.2)
                    st.rerun()

        self.update_online_status()

    def render_login_page(self):
        st.title("💬 Real-time Chat")

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")

                if submit:
                    success, message = self.login_user(username, password)
                    if success:
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)

        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                submit = st.form_submit_button("Register")

                if submit:
                    success, message = self.register_user(new_username, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    def run(self):
        if not st.session_state.user_id:
            self.render_login_page()
        else:
            self.render_chat_interface()


def main():
    st.set_page_config(
        page_title="Real-time Chat",
        layout="wide",
        page_icon="💬",
        initial_sidebar_state="expanded"
    )

    app = RealTimeChatApp()
    app.run()


if __name__ == "__main__":
    main()