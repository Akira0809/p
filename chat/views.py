from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from . import models, forms


# チャットルーム一覧を表示するビュー
class Index(LoginRequiredMixin, ListView):
    model = models.Room
    template_name = 'chat/index.html'
    context_object_name = 'rooms'
    paginate_by = 10

    # チャットルームの一覧をフィルタリングする
    def get_queryset(self):
        queryset = super().get_queryset()
        form = forms.SearchForm(self.request.GET or None)
        keywords = form.get_keywords()

        return queryset.filtering(user=self.request.user, keywords=keywords)

    # コンテキストデータに検索フォームを追加
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = forms.SearchForm(self.request.GET or None)

        return context


# チャットルームを作成するビュー
class CreateRoom(LoginRequiredMixin, CreateView):
    model = models.Room
    template_name = 'chat/room_form.html'
    form_class = forms.RoomForm
    success_url = reverse_lazy('chat:index')

    # フォームが有効な場合に実行
    def form_valid(self, form):
        form.instance.set_host(self.request.user)

        return super().form_valid(form)


# チャットルームのホストにのみ許可されるMixin
class OnlyRoomHostMixin(UserPassesTestMixin):
    raise_exception = True

    # ホストのみが許可されるかどうかをテスト
    def test_func(self):
        room = self.get_object()

        return room.is_host(self.request.user)


# チャットルームを更新するビュー
class UpdateRoom(LoginRequiredMixin, OnlyRoomHostMixin, UpdateView):
    model = models.Room
    template_name = 'chat/room_form.html'
    form_class = forms.RoomForm
    success_url = reverse_lazy('chat:index')


# チャットルームを削除するビュー
class DeleteRoom(LoginRequiredMixin, OnlyRoomHostMixin, DeleteView):
    model = models.Room
    success_url = reverse_lazy('chat:index')

    # 直接のアクセスを無視してリダイレクト
    def get(self, request, *args, **kwargs):
        return self.handle_no_permission()


# ユーザーが参加しているチャットルームにのみ許可されるMixin
class OnlyAssignedUserMixin(UserPassesTestMixin):
    raise_exception = True

    # 参加しているユーザーのみが許可されるかどうかをテスト
    def test_func(self):
        room = self.get_object()

        return room.is_assigned(self.request.user)


# チャットルームに入るビュー
class EnterRoom(LoginRequiredMixin, OnlyAssignedUserMixin, DetailView):
    model = models.Room
    template_name = 'chat/chat_room.html'
    context_object_name = 'room'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 自分がホストであるルームの一覧を取得
        rooms = models.Room.objects.filter(host=self.request.user)

        # コンテキストにルームの一覧を追加
        context['rooms'] = rooms

        return context

