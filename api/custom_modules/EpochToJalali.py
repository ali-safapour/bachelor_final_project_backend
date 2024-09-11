from datetime import datetime
import pytz
import jdatetime

def epoch_to_jalali(epoch_time):
    tehran_tz = pytz.timezone('Asia/Tehran')
    tehran_time = datetime.fromtimestamp(epoch_time, tz=tehran_tz)
    jalali_date = jdatetime.datetime.fromgregorian(datetime=tehran_time)
    formatted_jalali_date = jalali_date.strftime('%Y/%m/%d %H:%M')
    return formatted_jalali_date