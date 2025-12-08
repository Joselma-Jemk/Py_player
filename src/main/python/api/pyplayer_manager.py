from src.main.python.api.video_class import Video


class Playlist:
    def __init__(self, name: str):
        self.videos = []
        self.current_index = 0
        self.current_video = None
        self.name = name

    def add_video(self, video: Video) -> bool:
        if video not in self.videos:
            self.videos.append(video)
            return True
        return False

    def next_video(self) -> Video:
        if self.current_index >= len(self.videos):
            self.current_index = 0
        else:
            self.current_index += 1
        return self.videos[self.current_index]

    def previous_video(self) -> Video:
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = 0
        return self.videos[self.current_index]

    def save_state(self):
        pass

    def auto_save(self):
        pass

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
