from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model



# To login via username or email with password
class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            try:
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                
                return None

        if user.check_password(password) and self.user_can_login(user):
            return user
        return None

    def user_can_login(self, user):
        return user.is_active