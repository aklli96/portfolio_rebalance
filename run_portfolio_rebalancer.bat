@echo off
set current_dir=%CD%
REM Run the portfolio rebalancer GUI
call "%current_dir%\position_rebalancer\Scripts\activate"
python main.py
pause