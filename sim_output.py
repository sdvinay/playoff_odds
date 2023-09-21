import os
import pandas as pd


OUTPUT_BASEDIR = 'output'

def write_output(df, dir_name, job_id):
    output_dir = f'{OUTPUT_BASEDIR}/{dir_name}'
    if not os.path.exists (output_dir):
        os.makedirs(output_dir)
    df.reset_index().to_feather(f'{output_dir}/{job_id}.feather')


def gather_output(dir_name, index_flds):
    output_dir = f'{OUTPUT_BASEDIR}/{dir_name}'
    df = pd.concat([pd.read_feather(f'{output_dir}/{filename}') for filename in os.listdir(output_dir)], axis=0)
    if index_flds:
        df = df.set_index(index_flds)
    return df


def gather_results():
    return gather_output('standings', ['run_id', 'team'])


def gather_ranks():
    return gather_output('ranks', ['run_id', 'lg'])


def gather_summaries():
    summaries = gather_output('summaries', None)
    summary = summaries.groupby('team').sum()
    summary['max'] = summaries.groupby('team')['max'].max()
    summary['min'] = summaries.groupby('team')['min'].min()
    return summary

def gather_games():
    return gather_output('games', ['run_id', 'gamePk'])