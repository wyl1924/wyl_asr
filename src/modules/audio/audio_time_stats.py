#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理时间统计模块

提供音频处理时间的统计分析和报告功能，包括VAD、ASR和说话人识别的性能分析。
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import asdict
from .audio_processing_monitor import get_audio_processing_monitor, ProcessingTimeRecord


class AudioTimeStats:
    """音频处理时间统计分析器"""
    
    def __init__(self):
        self.monitor = get_audio_processing_monitor()
    
    def get_summary_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取指定时间范围内的汇总统计信息
        
        Args:
            hours: 统计时间范围（小时），默认24小时
            
        Returns:
            包含各项统计信息的字典
        """
        cutoff_time = time.time() - (hours * 3600)
        # 直接使用 records 属性而不是 get_recent_records 方法
        recent_records = [
            record for record in self.monitor.records
            if record.timestamp >= cutoff_time
        ]
        
        if not recent_records:
            return {
                "time_range": f"最近{hours}小时",
                "total_sessions": 0,
                "message": "暂无数据"
            }
        
        # 基本统计
        total_sessions = len(recent_records)
        successful_sessions = len([r for r in recent_records if r.vad_success and r.asr_success])
        success_rate = (successful_sessions / total_sessions) * 100 if total_sessions > 0 else 0
        
        # VAD统计
        vad_times = [r.vad_processing_time for r in recent_records if r.vad_processing_time is not None]
        vad_stats = self._calculate_time_stats(vad_times, "VAD")
        
        # ASR统计
        asr_times = [r.asr_processing_time for r in recent_records if r.asr_processing_time is not None]
        asr_stats = self._calculate_time_stats(asr_times, "ASR")
        
        # 说话人识别统计
        speaker_times = [r.speaker_processing_time for r in recent_records if r.speaker_processing_time is not None]
        speaker_stats = self._calculate_time_stats(speaker_times, "说话人识别")
        
        # 总处理时间统计
        total_times = [r.total_processing_time for r in recent_records if r.total_processing_time is not None]
        total_stats = self._calculate_time_stats(total_times, "总处理时间")
        
        # 音频时长统计
        audio_durations = [r.audio_duration for r in recent_records if r.audio_duration is not None]
        duration_stats = self._calculate_time_stats(audio_durations, "音频时长")
        
        return {
            "time_range": f"最近{hours}小时",
            "total_sessions": total_sessions,
            "successful_sessions": successful_sessions,
            "success_rate": round(success_rate, 2),
            "vad_stats": vad_stats,
            "asr_stats": asr_stats,
            "speaker_stats": speaker_stats,
            "total_processing_stats": total_stats,
            "audio_duration_stats": duration_stats,
            "generated_at": datetime.now().isoformat()
        }
    
    def _calculate_time_stats(self, times: List[float], name: str) -> Dict[str, Any]:
        """计算时间统计信息
        
        Args:
            times: 时间列表（毫秒）
            name: 统计项名称
            
        Returns:
            统计信息字典
        """
        if not times:
            return {
                "name": name,
                "count": 0,
                "message": "暂无数据"
            }
        
        times_sorted = sorted(times)
        count = len(times)
        
        return {
            "name": name,
            "count": count,
            "min": round(min(times), 2),
            "max": round(max(times), 2),
            "avg": round(sum(times) / count, 2),
            "median": round(times_sorted[count // 2], 2),
            "p95": round(times_sorted[int(count * 0.95)], 2),
            "p99": round(times_sorted[int(count * 0.99)], 2)
        }
    
    def get_performance_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """获取性能分析报告
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            性能分析报告
        """
        cutoff_time = time.time() - (hours * 3600)
        recent_records = [
            record for record in self.monitor.records
            if record.timestamp >= cutoff_time
        ]
        
        if not recent_records:
            return {
                "time_range": f"最近{hours}小时",
                "message": "暂无数据进行分析"
            }
        
        analysis = {
            "time_range": f"最近{hours}小时",
            "total_sessions": len(recent_records),
            "performance_insights": [],
            "recommendations": []
        }
        
        # 分析处理时间与音频时长的比例
        processing_ratios = []
        for record in recent_records:
            if record.total_processing_time and record.audio_duration and record.audio_duration > 0:
                ratio = record.total_processing_time / record.audio_duration
                processing_ratios.append(ratio)
        
        if processing_ratios:
            avg_ratio = sum(processing_ratios) / len(processing_ratios)
            analysis["performance_insights"].append({
                "metric": "处理时间/音频时长比例",
                "value": round(avg_ratio, 2),
                "description": f"平均处理时间是音频时长的{avg_ratio:.1f}倍"
            })
            
            if avg_ratio > 2.0:
                analysis["recommendations"].append("处理时间较长，建议优化模型推理性能")
            elif avg_ratio < 0.5:
                analysis["recommendations"].append("处理性能良好，实时性表现优秀")
        
        # 分析各阶段时间占比
        stage_times = {
            "vad": [r.vad_processing_time for r in recent_records if r.vad_processing_time],
            "asr": [r.asr_processing_time for r in recent_records if r.asr_processing_time],
            "speaker": [r.speaker_processing_time for r in recent_records if r.speaker_processing_time]
        }
        
        stage_analysis = {}
        for stage, times in stage_times.items():
            if times:
                avg_time = sum(times) / len(times)
                stage_analysis[stage] = {
                    "avg_time": round(avg_time, 2),
                    "count": len(times)
                }
        
        if stage_analysis:
            analysis["stage_analysis"] = stage_analysis
            
            # 找出最耗时的阶段
            max_stage = max(stage_analysis.items(), key=lambda x: x[1]["avg_time"])
            analysis["performance_insights"].append({
                "metric": "最耗时阶段",
                "value": max_stage[0],
                "description": f"{max_stage[0]}平均耗时{max_stage[1]['avg_time']}ms"
            })
        
        # 错误分析
        failed_records = [r for r in recent_records if not (r.vad_success and r.asr_success)]
        if failed_records:
            error_rate = (len(failed_records) / len(recent_records)) * 100
            analysis["performance_insights"].append({
                "metric": "错误率",
                "value": f"{error_rate:.1f}%",
                "description": f"共{len(failed_records)}次处理失败"
            })
            
            if error_rate > 5:
                analysis["recommendations"].append("错误率较高，建议检查模型状态和音频质量")
        
        return analysis
    
    def get_hourly_trends(self, hours: int = 24) -> Dict[str, Any]:
        """获取按小时的趋势分析
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            按小时的趋势数据
        """
        cutoff_time = time.time() - (hours * 3600)
        recent_records = [
            record for record in self.monitor.records
            if record.timestamp >= cutoff_time
        ]
        
        if not recent_records:
            return {
                "time_range": f"最近{hours}小时",
                "message": "暂无数据进行趋势分析"
            }
        
        # 按小时分组
        hourly_data = {}
        for record in recent_records:
            hour_key = datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d %H:00")
            if hour_key not in hourly_data:
                hourly_data[hour_key] = []
            hourly_data[hour_key].append(record)
        
        # 计算每小时的统计
        trends = []
        for hour, records in sorted(hourly_data.items()):
            hour_stats = {
                "hour": hour,
                "total_sessions": len(records),
                "successful_sessions": len([r for r in records if r.vad_success and r.asr_success]),
                "avg_total_time": 0,
                "avg_vad_time": 0,
                "avg_asr_time": 0,
                "avg_speaker_time": 0
            }
            
            # 计算平均时间
            total_times = [r.total_processing_time for r in records if r.total_processing_time]
            if total_times:
                hour_stats["avg_total_time"] = round(sum(total_times) / len(total_times), 2)
            
            vad_times = [r.vad_processing_time for r in records if r.vad_processing_time]
            if vad_times:
                hour_stats["avg_vad_time"] = round(sum(vad_times) / len(vad_times), 2)
            
            asr_times = [r.asr_processing_time for r in records if r.asr_processing_time]
            if asr_times:
                hour_stats["avg_asr_time"] = round(sum(asr_times) / len(asr_times), 2)
            
            speaker_times = [r.speaker_processing_time for r in records if r.speaker_processing_time]
            if speaker_times:
                hour_stats["avg_speaker_time"] = round(sum(speaker_times) / len(speaker_times), 2)
            
            trends.append(hour_stats)
        
        return {
            "time_range": f"最近{hours}小时",
            "hourly_trends": trends,
            "generated_at": datetime.now().isoformat()
        }
    
    def export_detailed_report(self, hours: int = 24, format: str = "json") -> str:
        """导出详细报告
        
        Args:
            hours: 报告时间范围（小时）
            format: 导出格式（json或text）
            
        Returns:
            报告内容字符串
        """
        summary = self.get_summary_stats(hours)
        analysis = self.get_performance_analysis(hours)
        trends = self.get_hourly_trends(hours)
        
        report_data = {
            "report_title": "音频处理时间统计报告",
            "generated_at": datetime.now().isoformat(),
            "time_range": f"最近{hours}小时",
            "summary_stats": summary,
            "performance_analysis": analysis,
            "hourly_trends": trends
        }
        
        if format == "json":
            return json.dumps(report_data, ensure_ascii=False, indent=2)
        elif format == "text":
            return self._format_text_report(report_data)
        else:
            raise ValueError("不支持的格式，请使用 'json' 或 'text'")
    
    def _format_text_report(self, report_data: Dict[str, Any]) -> str:
        """格式化文本报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"📊 {report_data['report_title']}")
        lines.append(f"📅 生成时间: {report_data['generated_at']}")
        lines.append(f"⏰ 统计范围: {report_data['time_range']}")
        lines.append("=" * 60)
        
        # 汇总统计
        summary = report_data['summary_stats']
        lines.append("\n📈 汇总统计:")
        lines.append(f"  总会话数: {summary.get('total_sessions', 0)}")
        lines.append(f"  成功会话数: {summary.get('successful_sessions', 0)}")
        lines.append(f"  成功率: {summary.get('success_rate', 0)}%")
        
        # 各阶段统计
        for stage_key, stage_name in [("vad_stats", "VAD"), ("asr_stats", "ASR"), ("speaker_stats", "说话人识别")]:
            stage_stats = summary.get(stage_key, {})
            if stage_stats.get('count', 0) > 0:
                lines.append(f"\n🔍 {stage_name}统计:")
                lines.append(f"  处理次数: {stage_stats['count']}")
                lines.append(f"  平均时间: {stage_stats['avg']}ms")
                lines.append(f"  最小时间: {stage_stats['min']}ms")
                lines.append(f"  最大时间: {stage_stats['max']}ms")
                lines.append(f"  P95时间: {stage_stats['p95']}ms")
        
        # 性能分析
        analysis = report_data['performance_analysis']
        if 'performance_insights' in analysis:
            lines.append("\n💡 性能洞察:")
            for insight in analysis['performance_insights']:
                lines.append(f"  • {insight['metric']}: {insight['value']} - {insight['description']}")
        
        if 'recommendations' in analysis:
            lines.append("\n🎯 优化建议:")
            for rec in analysis['recommendations']:
                lines.append(f"  • {rec}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


# 全局实例
_audio_time_stats = None

def get_audio_time_stats() -> AudioTimeStats:
    """获取音频时间统计实例"""
    global _audio_time_stats
    if _audio_time_stats is None:
        _audio_time_stats = AudioTimeStats()
    return _audio_time_stats