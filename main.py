# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import copy
import time
import re
import os
import random
import string
import json
import threading


class Spider:
    class Lesson:

        def __init__(self, name, code, teacher_name, Time, number):
            self.name = name
            self.code = code
            self.teacher_name = teacher_name
            self.time = Time
            self.number = number

        def show(self):
            print('  name:' + self.name + '  code:' + self.code + '  teacher_name:' + self.teacher_name + '  time:' + self.time)

    def __init__(self, url, verify_api_url):
        self.__uid = ''
        self.__real_base_url = ''
        self.__base_url = url
        self.__verify_api = verify_api_url
        self.__name = ''
        self.__base_data = {
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': '',
            'ddl_kcxz': '',
            'ddl_ywyl': '',
            'ddl_kcgs': '',
            'ddl_xqbs': '',
            'ddl_sksj': '',
            'TextBox1': '',
            'dpkcmcGrid:txtChoosePage': '1',
            'dpkcmcGrid:txtPageSize': '200',
        }
        self.__headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.62 Safari/537.36',
        }
        self.session = requests.Session()
        self.__now_lessons_number = 0
        self.__target_lesson = ''
        self.__selected_lesson = []
        self.__frequency = 0
        self.__lock = threading.RLock()
        self.__message_box = ''

    def __set_real_url(self):
        '''
        得到真实的登录地址（无Cookie）
        获取Cookie（有Cookie)
        :return: 该请求
        '''
        request = self.session.get(self.__base_url, headers=self.__headers)
        real_url = request.url
        if real_url != 'http://218.75.197.123:83/' and real_url != 'http://218.75.197.123:83/index.apsx':   # 湖南工业大学
            self.__real_base_url = real_url[:len(real_url) - len('default2.aspx')]
        else:
            if real_url.find('index') > 0:
                self.__real_base_url = real_url[:len(real_url) - len('index.aspx')]
            else:
                self.__real_base_url = real_url
        return request

    def __get_code(self):
        '''
        获取验证码
        :return: 验证码
        '''
        if self.__real_base_url != 'http://218.75.197.123:83/':
            request = self.session.get(self.__real_base_url + 'CheckCode.aspx', headers=self.__headers)
        else:
            request = self.session.get(self.__real_base_url + 'CheckCode.aspx?', headers=self.__headers)
        ran_str = ''.join(random.sample(string.ascii_letters + string.digits, 16))
        img_name = ran_str + '.png'
        with open(img_name, 'wb')as f:
            f.write(request.content)
        f.close()
        print('Loading checkcode')
        api_url = self.__verify_api
        fb = open(img_name, 'rb')
        files = {'image_file': (img_name, fb, 'application')}
        r = requests.post(url=api_url, files=files)
        fb.close()
        os.remove(img_name)
        res = json.loads(r.text)
        code = res['value']
        return code

    def __get_login_data(self, uid, password):
        '''
        得到登录包
        :param uid: 学号
        :param password: 密码
        :return: 含登录包的data字典

        '''
        self.__uid = uid
        request = self.__set_real_url()
        soup = BeautifulSoup(request.text, 'lxml')
        form_tag = soup.find('input')
        __VIEWSTATE = form_tag['value']
        code = self.__get_code()
        data = {
            '__VIEWSTATE': __VIEWSTATE,
            'txtUserName': self.__uid,
            'TextBox2': password,
            'txtSecretCode': code,
            'RadioButtonList1': '学生'.encode('gb2312'),
            'Button1': '',
            'lbLanguage': '',
            'hidPdrs': '',
            'hidsc': '',
        }
        return data

    def login(self, uid, password):
        '''
        外露的登录接口
        :param uid: 学号
        :param password: 密码
        :return: 抛出异常或返回是否登录成功的布尔值
        '''
        while True:
            data = self.__get_login_data(uid, password)
            if self.__real_base_url != 'http://218.75.197.123:83/':
                request = self.session.post(self.__real_base_url + 'default2.aspx', headers=self.__headers, data=data)
            else:
                request = self.session.post(self.__real_base_url + 'index.aspx', headers=self.__headers, data=data)
            soup = BeautifulSoup(request.text, 'lxml')
            if request.status_code != requests.codes.ok:
                print('4XX or 5XX Error,try to login again')
                time.sleep(0.5)
                continue
            if request.text.find('验证码不正确') > -1:
                print('验证码错误')
                continue
            if request.text.find('密码错误') > -1:
                print('密码错误')
                return False
            if request.text.find('用户名不存在') > -1:
                print('用户名错误')
                return False
            try:
                name_tag = soup.find(id='xhxm')
                self.__name = name_tag.string[:len(name_tag.string) - 2]
                print('欢迎' + self.__name)
                self.__enter_lessons_first()
                return True
            except Exception:
                print('未知错误，尝试再次登录')
                time.sleep(0.5)
                continue

    def __enter_lessons_first(self):
        '''
        首次进入选课界面
        :return: none
        '''
        data = {
            'xh': self.__uid,
            'xm': self.__name.encode('gb2312'),
            'gnmkdm': 'N121103',
        }
        self.__headers['Referer'] = self.__real_base_url + 'xs_main.aspx?xh=' + self.__uid
        request = self.session.get(self.__real_base_url + 'xf_xsqxxxk.aspx', params=data, headers=self.__headers)
        self.__headers['Referer'] = request.url
        soup = BeautifulSoup(request.text, 'lxml')
        self.__set__VIEWSTATE(soup)
        selected_lessons_pre_tag = soup.find('legend', text='已选课程')
        selected_lessons_tag = selected_lessons_pre_tag.next_sibling
        tr_list = selected_lessons_tag.find_all('tr')[1:]
        self.__now_lessons_number = len(tr_list)
        try:
            xq_tag = soup.find('select', id='ddl_xqbs')
            self.__base_data['ddl_xqbs'] = xq_tag.find('option')['value']
        except Exception:
            pass

    def __set__VIEWSTATE(self, soup):
        __VIEWSTATE_tag = soup.find('input', attrs={'name': '__VIEWSTATE'})
        self.__base_data['__VIEWSTATE'] = __VIEWSTATE_tag['value']

    def __get_lessons(self, soup):
        '''
        提取传进来的soup的课程信息
        :param soup:
        :return: 课程信息列表
        '''
        lesson_list = []
        lessons_tag = soup.find('table', id='kcmcGrid')
        lesson_tag_list = lessons_tag.find_all('tr')[1:]
        for lesson_tag in lesson_tag_list:
            td_list = lesson_tag.find_all('td')
            code = td_list[0].input['name']
            name = td_list[1].string
            teacher_name = td_list[3].string
            try:
                Time = td_list[4]['title']
            except KeyError:
                Time = "网课无课程周期"
            number = td_list[10].string
            lesson = self.Lesson(name, code, teacher_name, Time, number)
            lesson_list.append(lesson)
        return lesson_list

    def __search_lessons(self, lesson_name=''):
        '''
        搜索课程
        :param lesson_name: 课程名字
        :return: 课程列表
        '''
        self.__base_data['TextBox1'] = lesson_name.encode('gb2312')
        data = self.__base_data.copy()
        data['Button2'] = '确定'.encode('gb2312')
        request = self.session.post(self.__headers['Referer'], data=data, headers=self.__headers)
        soup = BeautifulSoup(request.text, 'lxml')
        self.__set__VIEWSTATE(soup)
        return self.__get_lessons(soup)

    def __select_lesson(self, lesson_list):
        '''
        开始选课
        :param lesson_list: 选的课程列表
        :return: none
        '''
        data = copy.deepcopy(self.__base_data)
        data['Button1'] = '  提交  '.encode('gb2312')
        while True:
            for lesson in lesson_list:
                try:
                    code = lesson.code
                    data[code] = 'on'
                    request = self.session.post(self.__headers['Referer'], data=data, headers=self.__headers, timeout=5)
                except Exception:
                    continue
                soup = BeautifulSoup(request.text, 'lxml')
                self.__set__VIEWSTATE(soup)
                error_tag = soup.html.head.script
                if error_tag is not None:
                    error_tag_text = error_tag.string
                    r = r"alert\('(.+?)'\);"
                    for s in re.findall(r, error_tag_text):
                        self.__message_box = s
                selected_lessons_pre_tag = soup.find('legend', text='已选课程')
                selected_lessons_tag = selected_lessons_pre_tag.next_sibling
                tr_list = selected_lessons_tag.find_all('tr')[1:]
                self.__now_lessons_number = len(tr_list)
                self.__lock.acquire()
                try:
                    for tr in tr_list:
                        td = tr.find('td')
                        if td in self.__selected_lesson:
                            pass
                        else:
                            self.__selected_lesson.append(td)
                    self.__frequency += 1
                    if self.__message_box == "该门课程已选！！":
                        self.__frequency = -1
                finally:
                    self.__lock.release()
            if self.__frequency == -1:
                break

    def run(self, uid, password, thread_num):
        '''
        开始运行
        :return: none
        '''
        if self.login(uid, password):
            print('请输入搜索课程名字，直接回车则显示全部可选课程')
            lesson_name = input()
            lesson_list = self.__search_lessons(lesson_name)
            print('请输入想选的课的id，id为每门课程开头的数字,如果没有课程显示，代表公选课暂无')
            for i in range(len(lesson_list)):
                print(i, end='')
                lesson_list[i].show()
            select_id = int(input())
            lesson_list = lesson_list[select_id:select_id + 1]
            self.__target_lesson = lesson_list[0].name
            thread_list = list()
            for i in range(thread_num):
                thread_list.append(threading.Thread(target=self.__select_lesson, args=(lesson_list,)))
            thread_list.append(threading.Thread(target=self.status_table, args=()))
            for i in range(thread_num+1):
                thread_list[i].start()
            for i in range(thread_num+1):
                thread_list[i].join()

    def status_table(self):
        while True:
            selected_lesson = self.__selected_lesson
            title = "已选课程："
            status = "当前状态：" + "正在抢" + self.__target_lesson
            message = self.__message_box
            # 创建一个25*9的列表
            table = [[[] for i in range(25)] for j in range(10)]
            for i in range(0, 10, 2):
                table[i][0] = '+'
                table[i][-1] = '+'
                for j in range(1, 24):
                    table[i][j] = '--'
            for i in range(1, 9, 2):
                table[i][0] = '|'
                table[i][-1] = '|'
            for i in range(len(title)):
                table[1][10+i] = title[i]
            for i in range(len(selected_lesson)):
                for j in range(len(selected_lesson[i].text)):
                    table[3+(2*i)][2+j] = selected_lesson[i].text[j]
            for i in range(len(status)):
                table[-3][1+i] = status[i]
            if self.__frequency == -1:
                frequency = "抢课完成"
            else:
                frequency = message + "已经抢了 " + str(self.__frequency) + "次"
            for i in range(len(frequency)):
                table[-1][i] = frequency[i]
            # 列表的个数
            y = len(table)
            # 列表中元素的个数
            x = len(table[0])
            # 创建一个字符串构成的表格
            table_string = ''
            for i in range(y):
                for j in range(x):
                    if table[i][j]:
                        table_string += str(table[i][j])
                    else:
                        table_string += '  '
                table_string += '\n'
            os.system('cls')
            print(table_string, end='')
            time.sleep(3)


if __name__ == '__main__':
    print('尝试登录...')
    with open('config.json', encoding='utf-8')as f:
        config = json.load(f)
    url = config['url']
    uid = config['student_number']
    password = config['password']
    thread_num = int(config['thread'])
    verify_api_url = config['verify_api_url']
    spider = Spider(url, verify_api_url)
    spider.run(uid, password, thread_num)
    os.system("pause")
