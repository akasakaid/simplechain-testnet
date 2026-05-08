import os
import sys
import json
import httpx
import time
from web3 import Account, Web3
from eth_account.messages import encode_defunct
from datetime import datetime
from base64 import b64decode


def log(msg):
    now = datetime.now().isoformat(" ").split(".")[0]
    print(f"[{now}] {msg}")


def http(ses, url, data=None):
    for _ in range(5):
        try:
            if data is None:
                res = ses.get(url=url)
            elif data == "":
                res = ses.post(url=url)
            else:
                res = ses.post(url=url, data=data)
            if (
                not os.path.exists("http.log")
                or os.path.getsize("http.log") / 1024 > 2048
            ):
                open("http.log", "w").write("")
            with open("http.log", "a") as w:
                w.write(f"{res.text}\n")
            return res
        except KeyboardInterrupt:
            sys.exit()
        except:
            continue


def countdown(t):
    for i in range(t, 0, -1):
        minute, second = divmod(i, 60)
        hour, minute = divmod(minute, 60)
        hour = str(hour).zfill(2)
        minute = str(minute).zfill(2)
        second = str(second).zfill(2)
        print(f"wait until {hour}:{minute}:{second} ", flush=True, end="\r")
        time.sleep(1)


LINE = "~" * 50
NONCE_URL = "https://task.simplechain.com/api/v1/get/nonce"
LOGIN_URL = "https://task.simplechain.com/api/v1/login"
LIST_URL = "https://task.simplechain.com/api/v1/task/list"
INFO_URL = "https://task.simplechain.com/api/v1/user/get/info"
COMPLETE_TASK_URL = "https://task.simplechain.com/api/v1/task/complete"
CHECKIN_URL = "https://task.simplechain.com/api/v1/campaign/checkin"
HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "task.simplechain.com",
    "Origin": "https://task.simplechain.com",
    "Pragma": "no-cache",
    "Referer": "https://task.simplechain.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
    "content-type": "application/json",
    "sec-ch-ua": '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class TKM:
    @staticmethod
    def load(key):
        with open("tokens.json") as r:
            tokens = json.loads(r.read())
            token = tokens.get(key)
            return token

    @staticmethod
    def save(key, value):
        with open("tokens.json") as r:
            tokens = json.loads(r.read())
            tokens[key] = value
            with open("tokens.json", "w") as w:
                w.write(json.dumps(tokens, indent=4))

    @staticmethod
    def is_expired(token=None):
        if token is None:
            return True
        header, b64body, sign = token.split(".")
        body = json.loads(b64decode(b64body + "=="))
        exp = body.get("exp")
        now = datetime.now().timestamp()
        if now > exp:
            return True
        return False


class SimpleChain:
    def __init__(self, privatekey, proxy=None):
        self.wallet = Account.from_key(privatekey)
        self.ses = httpx.Client(proxy=proxy, headers=HEADERS)

    def login(self):
        data = {"address": self.wallet.address}
        res = http(ses=self.ses, url=NONCE_URL, data=json.dumps(data))
        if res is None:
            return "bad_proxy"
        nonce = res.json().get("data", {}).get("nonce")
        if nonce is None:
            log("failed to obtain nonce !")
            return False
        log("successfully obtained the nonce !")
        message = f"""Welcome to SimpleChain!

Click to sign in and accept the SimpleChain Terms of Service.

This request will not trigger a blockchain transaction or cost any gas fees.

Nonce: {nonce}"""
        encode_message = encode_defunct(text=message)
        _signature = Account.sign_message(encode_message, private_key=self.wallet.key)
        signature = Web3.to_hex(_signature.signature)
        data = {
            "signature": signature,
            "message": message,
            "address": self.wallet.address,
        }
        res = http(ses=self.ses, url=LOGIN_URL, data=json.dumps(data))
        if res is None:
            return "bad_proxy"
        token = res.json().get("data", {}).get("token")
        if token is None:
            log("failed to log in !")
            return False
        log("successfully logged in !")
        TKM.save(key=self.wallet.address[:10], value=token)
        return True

    def info(self):
        res = http(ses=self.ses, url=INFO_URL)
        if res is None:
            return "bad_proxy"
        available_point = res.json().get("data", {}).get("availablePoints")
        ban_status = res.json().get("data", {}).get("banStatus")
        ban_msg = res.json().get("data", {}).get("banMessage")
        level = res.json().get("data", {}).get("level")
        username = res.json().get("data", {}).get("userName")
        log(f"username : {username}, level : {level}")
        log(f"total point : {available_point}")
        log(f"ban status : {False if ban_status == 0 else True}")
        if ban_status:
            log(f"ban message : {ban_msg}")
            return False
        return True

    def do_daily(self):
        token = TKM.load(key=self.wallet.address[:10])
        if token is None:
            result = self.login()
            if result is not True:
                return result
            token = TKM.load(key=self.wallet.address[:10])
        is_expired = TKM.is_expired(token=token)
        if is_expired:
            result = self.login()
            if result is not True:
                return result
            token = TKM.load(key=self.wallet.address[:10])
        self.ses.headers.update({"authorization": f"Bearer {token}"})
        if not self.info():
            return False
        res = http(ses=self.ses, url=LIST_URL)
        if res is None:
            return "bad_proxy"
        tasks = res.json().get("data", {}).get("tasks")
        for task in tasks:
            task_type = task.get("taskType")
            task_code = task.get("taskCode")
            task_id = task.get("taskId")
            completion_status = task.get("completionStatus")
            task_name = task.get("taskName")
            if task_type == "DAILY":
                log(f"task name : {task_name}, task_id : {task_id}")
                if completion_status == "COMPLETED_TODAY":
                    log("The task has been completed !")
                    continue
                if task_code == "DAILY_CHECK_IN":
                    res = http(ses=self.ses, url=CHECKIN_URL, data=json.dumps({}))
                    if res is None:
                        return "bad_proxy"
                    total_reward = res.json().get("data", {}).get("totalReward")
                    total_point = res.json().get("data", {}).get("totalPoints")
                    log(f"reward : {total_reward}, total point : {total_point}")
                if task_code == "ACCESS_LINK":
                    res = http(
                        ses=self.ses,
                        url=COMPLETE_TASK_URL,
                        data=json.dumps({"taskId": task_id}),
                    )
                    if res is None:
                        return "bad_proxy"
                    total_reward = res.json().get("data", {}).get("rewardPoints")
                    log(f"reward : {total_reward}")


def main():
    if not os.path.exists("tokens.json"):
        open("tokens.json", "w").write("{}")
    os.system("cls" if os.name == "nt" else "clear")
    banner = """
┏━┓╺┳┓┏━┓┏━┓┏━┓┏━┓ ┏┓┏━╸┏━╸╺┳╸
┗━┓ ┃┃┗━┓┣━┛┣┳┛┃ ┃  ┃┣╸ ┃   ┃ 
┗━┛╺┻┛┗━┛╹  ╹┗╸┗━┛┗━┛┗━╸┗━╸ ╹ 
    Simplechain Testnet
@AkasakaID | join t.me/sdsproject"""
    menu = """
Menu :
1. daily checkin [loop 24/7]
"""
    print(banner)
    print(menu)
    print(LINE)
    option = input("enter menu number : ")
    print(LINE)
    if option == "1":
        pk_file = input("enter the private key file\n--> ")
        if not os.path.exists(pk_file):
            print(f"the {pk_file} file is missing. please double-check the filename!")
            sys.exit()
        proxy_file = (
            input(
                "enter the proxy file if you want to use it; otherwise, press enter\n--> "
            )
            or None
        )
        if proxy_file is not None:
            if not os.path.exists(proxy_file):
                print(
                    f"the {proxy_file} file is missing. please double-check the filename !"
                )
                sys.exit()
            proxies = open(proxy_file).read().splitlines()
        else:
            proxies = []
        print(LINE)
        pks = open(pk_file).read().splitlines()
        print(f"total privatekey : {len(pks)}")
        print(f"total proxy : {len(proxies)}")
        print(LINE)
        while True:
            p = 0
            st = int(time.time())
            for n, pk in enumerate(pks):
                log(f"wallet-{n + 1}")
                while True:
                    proxy = None if len(proxies) == 0 else proxies[p % len(proxies)]
                    result = SimpleChain(privatekey=pk, proxy=proxy).do_daily()
                    if result == "bad_proxy":
                        p += 1
                        continue
                    p += 1
                    break
                print(LINE)
            et = int(time.time())
            twentyfourhours = (24 * 3600) - (et - st)
            countdown(twentyfourhours)

    else:
        print("that's funny, you entered the wrong number !")
        sys.exit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
