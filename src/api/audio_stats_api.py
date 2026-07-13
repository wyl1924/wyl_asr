#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理时间统计API

提供音频处理时间统计的REST API接口。
"""

import json
from flask import Blueprint, request, jsonify
from ..modules.audio.audio_time_stats import get_audio_time_stats
from ..modules.audio.audio_processing_monitor import get_audio_processing_monitor

# 创建蓝图
audio_stats_bp = Blueprint('audio_stats', __name__, url_prefix='/api/audio-stats')


@audio_stats_bp.route('/summary', methods=['GET'])
def get_summary_stats():
    """获取汇总统计信息
    
    Query Parameters:
        hours (int): 统计时间范围（小时），默认24小时
    
    Returns:
        JSON: 汇总统计信息
    """
    try:
        hours = request.args.get('hours', 24, type=int)
        if hours <= 0 or hours > 168:  # 最多7天
            return jsonify({
                'code': 400,
                'message': '时间范围必须在1-168小时之间',
                'data': None
            }), 400
        
        stats = get_audio_time_stats()
        summary = stats.get_summary_stats(hours)
        
        return jsonify({
            'code': 200,
            'message': '获取汇总统计成功',
            'data': summary
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取统计信息失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/performance', methods=['GET'])
def get_performance_analysis():
    """获取性能分析报告
    
    Query Parameters:
        hours (int): 分析时间范围（小时），默认24小时
    
    Returns:
        JSON: 性能分析报告
    """
    try:
        hours = request.args.get('hours', 24, type=int)
        if hours <= 0 or hours > 168:
            return jsonify({
                'code': 400,
                'message': '时间范围必须在1-168小时之间',
                'data': None
            }), 400
        
        stats = get_audio_time_stats()
        analysis = stats.get_performance_analysis(hours)
        
        return jsonify({
            'code': 200,
            'message': '获取性能分析成功',
            'data': analysis
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取性能分析失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/trends', methods=['GET'])
def get_hourly_trends():
    """获取按小时的趋势分析
    
    Query Parameters:
        hours (int): 分析时间范围（小时），默认24小时
    
    Returns:
        JSON: 按小时的趋势数据
    """
    try:
        hours = request.args.get('hours', 24, type=int)
        if hours <= 0 or hours > 168:
            return jsonify({
                'code': 400,
                'message': '时间范围必须在1-168小时之间',
                'data': None
            }), 400
        
        stats = get_audio_time_stats()
        trends = stats.get_hourly_trends(hours)
        
        return jsonify({
            'code': 200,
            'message': '获取趋势分析成功',
            'data': trends
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取趋势分析失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/report', methods=['GET'])
def export_report():
    """导出详细报告
    
    Query Parameters:
        hours (int): 报告时间范围（小时），默认24小时
        format (str): 导出格式（json或text），默认json
    
    Returns:
        JSON或文本: 详细报告
    """
    try:
        hours = request.args.get('hours', 24, type=int)
        format_type = request.args.get('format', 'json', type=str).lower()
        
        if hours <= 0 or hours > 168:
            return jsonify({
                'code': 400,
                'message': '时间范围必须在1-168小时之间',
                'data': None
            }), 400
        
        if format_type not in ['json', 'text']:
            return jsonify({
                'code': 400,
                'message': '格式必须是json或text',
                'data': None
            }), 400
        
        stats = get_audio_time_stats()
        report = stats.export_detailed_report(hours, format_type)
        
        if format_type == 'text':
            return report, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        else:
            return jsonify({
                'code': 200,
                'message': '导出报告成功',
                'data': json.loads(report)
            })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'导出报告失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/recent-records', methods=['GET'])
def get_recent_records():
    """获取最近的处理记录
    
    Query Parameters:
        limit (int): 记录数量限制，默认100，最大1000
    
    Returns:
        JSON: 最近的处理记录列表
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        if limit <= 0 or limit > 1000:
            return jsonify({
                'code': 400,
                'message': '记录数量限制必须在1-1000之间',
                'data': None
            }), 400
        
        monitor = get_audio_processing_monitor()
        records = monitor.get_recent_records(limit)
        
        # 转换为字典格式
        records_data = []
        for record in records:
            record_dict = {
                'session_id': record.session_id,
                'start_time': record.start_time,
                'end_time': record.end_time,
                'audio_size': record.audio_size,
                'audio_duration': record.audio_duration,
                'vad_time': record.vad_time,
                'asr_time': record.asr_time,
                'asr_mode': record.asr_mode,
                'speaker_recognition_time': record.speaker_recognition_time,
                'total_time': record.total_time,
                'success': record.success,
                'error_message': record.error_message
            }
            records_data.append(record_dict)
        
        return jsonify({
            'code': 200,
            'message': f'获取最近{len(records_data)}条记录成功',
            'data': {
                'records': records_data,
                'total_count': len(records_data)
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取记录失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/reset', methods=['POST'])
def reset_monitor():
    """重置监控数据
    
    Returns:
        JSON: 重置结果
    """
    try:
        monitor = get_audio_processing_monitor()
        monitor.reset()
        
        return jsonify({
            'code': 200,
            'message': '监控数据重置成功',
            'data': None
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'重置监控数据失败: {str(e)}',
            'data': None
        }), 500


@audio_stats_bp.route('/monitor-status', methods=['GET'])
def get_monitor_status():
    """获取监控器状态
    
    Returns:
        JSON: 监控器状态信息
    """
    try:
        monitor = get_audio_processing_monitor()
        stats = monitor.get_stats()
        
        return jsonify({
            'code': 200,
            'message': '获取监控器状态成功',
            'data': {
                'total_sessions': stats['total_sessions'],
                'successful_sessions': stats['successful_sessions'],
                'failed_sessions': stats['failed_sessions'],
                'success_rate': stats['success_rate'],
                'avg_processing_time': stats['avg_processing_time'],
                'avg_audio_duration': stats['avg_audio_duration'],
                'monitor_start_time': monitor.start_time,
                'records_count': len(monitor.records)
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取监控器状态失败: {str(e)}',
            'data': None
        }), 500