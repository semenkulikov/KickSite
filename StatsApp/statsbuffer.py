from ServiceApp import Singleton


class StatsBuffer:
    '''
    __stats_buffer = {
                        "twitch": {
                            "user1": [
                                {"time": 1, "message": 2, "channel": 3, "account": 4},
                                {"time": 1, "message": 2, "channel": 3, "account": 4},
                                {"time": 1, "message": 2, "channel": 3, "account": 4},
                                {"time": 1, "message": 2, "channel": 3, "account": 4},
                                {"time": 1, "message": 2, "channel": 3, "account": 4},
                            ],
                            "user2": [],
                        },
                    }
    '''
    __stats_buffer = dict()

    @classmethod
    def add(cls):
        pass